#!/usr/bin/env python3
"""
Proxy Stratum → FPGA
- MODO TESTE : difficulty forçada + share inicial (dashboard)
- MODO REAL  : difficulty real da pool
- Hashrate LOCAL exibido em tempo real
"""

import socket
import json
import serial
import time
import struct
import binascii
import hashlib
import sys

# =========================================================
# CONFIGURAÇÃO
# =========================================================

POOL_HOST = "public-pool.io"
POOL_PORT = 3333
POOL_USER = "bc1qj9ap5kwqtu5498ssca6apxdu7zaju0rqty8k0p.EmbarcaMiner"
POOL_PASS = "x"

UART_PORT = "/dev/ttyACM0"
UART_BAUD = 115200

# Difficulty extremamente fácil (modo TESTE)
TEST_TARGET_BITS = 0x207fffff

# =========================================================
# SELEÇÃO DE MODO
# =========================================================

print("""
Selecione o modo:
  1 - MODO TESTE (difficulty baixa / dashboard)
  2 - MODO REAL  (difficulty da pool)
""")

mode = input(">>> ").strip()

if mode == "1":
    MODE_TEST = True
    print("\n Iniciando em MODO TESTE\n")
elif mode == "2":
    MODE_TEST = False
    print("\n Iniciando em MODO REAL\n")
else:
    print("Modo inválido.")
    sys.exit(1)

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def bits_to_target(nbits_hex):
    n = int(nbits_hex, 16)
    exp = n >> 24
    mant = n & 0xFFFFFF
    return mant << (8 * (exp - 3))

def target_to_words_le(target):
    return [(target >> (32 * i)) & 0xffffffff for i in range(8)]

def calculate_merkle_root(coinbase_hex, branches):
    h = hashlib.sha256(
        hashlib.sha256(binascii.unhexlify(coinbase_hex)).digest()
    ).digest()
    for b in branches:
        h = hashlib.sha256(
            hashlib.sha256(h + binascii.unhexlify(b)).digest()
        ).digest()
    return h

def build_header(version, prevhash, merkle_root, ntime, nbits, nonce):
    return (
        struct.pack("<I", int(version, 16)) +
        binascii.unhexlify(prevhash)[::-1] +
        merkle_root[::-1] +
        struct.pack("<I", int(ntime, 16)) +
        struct.pack("<I", int(nbits, 16)) +
        struct.pack("<I", nonce)
    )

def format_hashrate(h):
    if h < 1e3:
        return f"{h:.2f} H/s"
    elif h < 1e6:
        return f"{h/1e3:.2f} kH/s"
    elif h < 1e9:
        return f"{h/1e6:.2f} MH/s"
    else:
        return f"{h/1e9:.2f} GH/s"

# =========================================================
# FPGA
# =========================================================

class FPGAManager:
    def __init__(self, port, baud):
        self.uart = serial.Serial(port, baud, timeout=1)
        time.sleep(2)
        print(f" FPGA conectado em {port}")

    def clear_buffer(self):
        if self.uart.in_waiting:
            self.uart.read(self.uart.in_waiting)

    def send_command(self, cmd, clear=True):
        if clear:
            self.clear_buffer()

        self.uart.write((cmd + "\n").encode())
        time.sleep(0.05)

        resp = b""
        start = time.time()
        while time.time() - start < 2:
            if self.uart.in_waiting:
                resp += self.uart.read(self.uart.in_waiting)
                if b"RUNTIME>" in resp:
                    break
            time.sleep(0.01)

        return "\n".join(
            l.strip() for l in resp.decode(errors="ignore").splitlines()
            if l.strip() and not l.startswith(cmd) and not l.startswith("RUNTIME>")
        )

    def send_job(self, header_hex, nbits_hex):
        target = bits_to_target(nbits_hex)
        words = target_to_words_le(target)

        print("    Target:")
        for i, w in enumerate(words):
            print(f"      w{i}: 0x{w:08x}")

        target_hex = "".join(struct.pack("<I", w).hex() for w in words)

        self.send_command("miner_clear")
        time.sleep(0.1)
        self.send_command(f"miner_job {header_hex}{target_hex}")
        print("    Job enviado ao FPGA")

    def wait_for_nonce(self, timeout=30):
        print("    Aguardando FPGA")

        start = time.time()
        hashes_est = 0

        HASHES_POR_SEGUNDO_EST = 5000  # AJUSTE depois

        for _ in range(timeout * 2):
            time.sleep(0.5)

            # estimativa
            hashes_est += HASHES_POR_SEGUNDO_EST * 0.5
            elapsed = time.time() - start

            hashrate = hashes_est / elapsed if elapsed > 0 else 0

            print(
                f"\r Hashrate local: {hashrate/1e3:6.2f} kH/s | Hashes: {int(hashes_est)}",
                end="",
                flush=True
            )

            resp = self.send_command("miner_status", clear=False)
            if resp:
                for line in resp.splitlines():
                    if "Nonce encontrado" in line and "(" in line:
                        print(f"\n   📄 {line}")
                        nonce_hex = line.split("(")[1].split(")")[0]
                        return int(nonce_hex, 16)

        print("\n    Timeout")
        return None

# =========================================================
# STRATUM
# =========================================================

def connect_pool():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((POOL_HOST, POOL_PORT))

    sock.send(json.dumps({
        "id": 1,
        "method": "mining.subscribe",
        "params": ["fpga-proxy/1.0"]
    }).encode() + b"\n")

    time.sleep(0.5)

    sock.send(json.dumps({
        "id": 2,
        "method": "mining.authorize",
        "params": [POOL_USER, POOL_PASS]
    }).encode() + b"\n")

    return sock

# =========================================================
# MAIN
# =========================================================

def main():
    fpga = FPGAManager(UART_PORT, UART_BAUD)
    sock = connect_pool()

    buffer = ""
    extranonce1 = ""
    extranonce2_size = 0
    extranonce_counter = 0
    worker_registered = False

    total_hashes = 0
    global_start = time.time()

    print(" Proxy rodando")

    while True:
        data = sock.recv(4096)
        if not data:
            sock = connect_pool()
            continue

        buffer += data.decode()

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if not line.strip():
                continue

            msg = json.loads(line)

            if msg.get("id") == 1:
                extranonce1 = msg["result"][1]
                extranonce2_size = msg["result"][2]
                print(f" Subscribed extranonce1={extranonce1}")

            elif msg.get("method") == "mining.notify":
                p = msg["params"]
                job_id, prevhash, c1, c2, branches, version, nbits, ntime = p[:8]

                effective_nbits = (
                    f"{TEST_TARGET_BITS:08x}" if MODE_TEST else nbits
                )

                print(f"\n JOB {job_id}")
                print(f"   nbits pool={nbits}")
                print(f"   nbits efetivo={effective_nbits}")

                extranonce2 = f"{extranonce_counter:0{extranonce2_size*2}x}"
                extranonce_counter += 1

                coinbase = c1 + extranonce1 + extranonce2 + c2
                merkle = calculate_merkle_root(coinbase, branches)

                header = build_header(
                    version, prevhash, merkle,
                    ntime, effective_nbits, 0
                )

                fpga.send_job(header.hex(), effective_nbits)

                # Share forçado (apenas 1 vez no modo TESTE)
                if MODE_TEST and not worker_registered:
                    print("    Enviando SHARE FORÇADO (dashboard)")
                    submit = {
                        "id": 999,
                        "method": "mining.submit",
                        "params": [
                            POOL_USER,
                            job_id,
                            extranonce2,
                            ntime,
                            "00000000"
                        ]
                    }
                    sock.send((json.dumps(submit) + "\n").encode())
                    worker_registered = True

                job_start = time.time()
                nonce = fpga.wait_for_nonce(60)
                elapsed = time.time() - job_start

                if nonce is None:
                    continue

                hashes = nonce + 1
                total_hashes += hashes

                hrate = hashes / elapsed
                avg_hrate = total_hashes / (time.time() - global_start)

                print(f"    Hashes testados: {hashes}")
                print(f"    Hashrate local: {format_hashrate(hrate)}")
                print(f"    Hashrate médio: {format_hashrate(avg_hrate)}")

                submit = {
                    "id": extranonce_counter,
                    "method": "mining.submit",
                    "params": [
                        POOL_USER,
                        job_id,
                        extranonce2,
                        ntime,
                        f"{nonce:08x}"
                    ]
                }

                sock.send((json.dumps(submit) + "\n").encode())
                print("    SHARE enviado")

if __name__ == "__main__":
    main()
