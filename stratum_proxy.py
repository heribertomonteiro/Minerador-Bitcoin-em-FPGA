#!/usr/bin/env python3
"""
Proxy entre pool Stratum (via internet do PC) e minerador FPGA (via UART).
"""
import socket
import json
import serial
import time
import struct
import binascii
import hashlib

# ============================================
# CONFIGURAÇÃO - Braiins Pool (Slush Pool)
# ============================================

POOL_HOST = "stratum.braiins.com"
POOL_PORT = 3333
POOL_USER = "heriberto.worker1"
POOL_PASS = "anything123"

# Configurações UART
UART_PORT = "/dev/ttyACM0"
UART_BAUD = 115200

# Verbosidade de logs
VERBOSE = True

# Modo de operação
# - DEMO: facilita o alvo para encontrar nonces com frequência.
#         Shares enviados à pool vão quase sempre ser REJEITADOS,
#         mas você consegue testar o fluxo completo.
# - REAL: usa exatamente o target da pool (nbits). Shares aceitos
#         serão extremamente raros em uma única FPGA.
DEMO_MODE = False

# Fator de facilitação no modo DEMO (target_local = target_pool * DEMO_FACTOR)
# Valores grandes facilitam MUITO o alvo (encontrar mais rápido, mas share inválido).
# TURBO: usa fator bem alto para encontrar nonces em poucos segundos.
DEMO_FACTOR = 2**16  # ~65 mil vezes mais fácil que o target da pool

# Dificuldade atual de share informada pela pool (mining.set_difficulty)
current_difficulty = 1.0


def debug_print(*args):
    """Imprime logs adicionais quando VERBOSE estiver habilitado."""
    if VERBOSE:
        print("[DEBUG]", *args)

def connect_pool():
    """Conecta à pool via Stratum."""
    print(f"Conectando à pool {POOL_HOST}:{POOL_PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    
    try:
        sock.connect((POOL_HOST, POOL_PORT))
    except Exception as e:
        print(f"Erro ao conectar: {e}")
        return None
    
    subscribe = {"id": 1, "method": "mining.subscribe", "params": ["proxy_fpga/1.0"]}
    debug_print("SEND subscribe:", subscribe)
    sock.send((json.dumps(subscribe) + "\n").encode())
    
    time.sleep(0.5)
    authorize = {"id": 2, "method": "mining.authorize", "params": [POOL_USER, POOL_PASS]}
    debug_print("SEND authorize:", authorize)
    sock.send((json.dumps(authorize) + "\n").encode())
    
    return sock

def calculate_merkle_root(coinbase_hex, merkle_branches):
    """Calcula merkle root."""
    h = hashlib.sha256(hashlib.sha256(binascii.unhexlify(coinbase_hex)).digest()).digest()
    for branch in merkle_branches:
        h = hashlib.sha256(hashlib.sha256(h + binascii.unhexlify(branch)).digest()).digest()
    return h


def difficulty_to_target_words(difficulty: float):
    """Converte dificuldade de share em target de 256 bits (8 words de 32 bits).

    Fórmula aproximada baseada em diff1_target do Bitcoin:
    target = diff1_target / difficulty
    onde diff1_target = 0x00000000FFFF0000....
    """

    if difficulty <= 0:
        difficulty = 1.0

    diff1_target_int = int(
        0x00000000FFFF0000000000000000000000000000000000000000000000000000
    )

    target_int = int(diff1_target_int / float(difficulty))

    # Limita a 256 bits
    target_int = max(0, min(target_int, (1 << 256) - 1))

    target_bytes_be = target_int.to_bytes(32, byteorder="big")

    target_words = []
    for i in range(0, 32, 4):
        word_le = int.from_bytes(target_bytes_be[i:i+4], byteorder="little")
        target_words.append(word_le)

    return target_words

def bits_to_target(nbits_hex, difficulty_divisor=1.0):
    """Converte nbits (compact target) em 8 palavras de 32 bits.

    - Em modo REAL: usa o target exato da pool.
    - Em modo DEMO: multiplica o target por DEMO_FACTOR para facilitar
      o alvo (mais soluções locais, porém normalmente inválidas para a pool).
    """
    nbits = int(nbits_hex, 16)
    exp = (nbits >> 24) & 0xFF
    mant = nbits & 0xFFFFFF

    # Target inteiro de 256 bits em big-endian, como no Bitcoin
    target_int = mant * (1 << (8 * (exp - 3)))

    if difficulty_divisor and difficulty_divisor != 1.0:
        target_int = int(target_int // difficulty_divisor)

    # Aplica facilitação em modo DEMO (target_local = target_pool * DEMO_FACTOR)
    if DEMO_MODE:
        target_int = target_int * DEMO_FACTOR

    # Limita a 256 bits
    target_int = max(0, min(target_int, (1 << 256) - 1))

    target_bytes_be = target_int.to_bytes(32, byteorder="big")

    # Converte para 8 palavras de 32 bits em little-endian por palavra,
    # que é o formato esperado pelo firmware (miner_job_cmd).
    target_words = []
    for i in range(0, 32, 4):
        word_le = int.from_bytes(target_bytes_be[i:i+4], byteorder="little")
        target_words.append(word_le)

    return target_words

def build_header_hex(version, prevhash, merkle_root, ntime, nbits):
    """Monta header de 80 bytes em hex."""
    v = struct.pack("<I", int(version, 16))
    ph = binascii.unhexlify(prevhash)[::-1]
    mr = merkle_root[::-1]
    nt = struct.pack("<I", int(ntime, 16))
    nb = struct.pack("<I", int(nbits, 16))
    nc = struct.pack("<I", 0)
    
    header = v + ph + mr + nt + nb + nc
    return binascii.hexlify(header).decode()

def send_job_to_fpga(uart, header_hex, target_words):
    """Envia job para FPGA via comando miner_job."""
    target_hex = ''.join([f'{w:08x}' for w in target_words])
    job_data = header_hex + target_hex
    
    if len(job_data) != 224:
        print(f"ERRO: Job tem {len(job_data)} caracteres, esperado 224!")
        return
    
    cmd = f"miner_job {job_data}\n"
    print(f"Enviando job para FPGA ({len(job_data)} caracteres)")
    debug_print("HEADER (primeiros 40 chars):", header_hex[:40])
    debug_print("TARGET words:", [f"0x{w:08x}" for w in target_words])
    
    chunk_size = 64
    for i in range(0, len(cmd), chunk_size):
        chunk = cmd[i:i+chunk_size]
        uart.write(chunk.encode())
        time.sleep(0.05)
    
    time.sleep(1)
    
    uart.write(b"\n")
    time.sleep(0.2)
    response = uart.read(1024).decode(errors='ignore')
    debug_print("FPGA resp (apos job):", response.replace("\n", "\\n"))
    
    if "Carregando job da pool" in response:
        print("✓ Job recebido pela FPGA")
    elif "Erro" in response:
        print(f"✗ FPGA reportou erro: {response}")

def wait_for_result(uart, timeout=60):
    """Espera resultado da FPGA."""
    start = time.time()
    checks = 0
    while time.time() - start < timeout:
        time.sleep(0.5)
        uart.write(b"miner_status\n")
        time.sleep(0.2)
        
        response = uart.read(2048).decode(errors='ignore')
        checks += 1
        
        if checks % 10 == 0:
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] Minerando...")
        
        if "found=1" in response and "Nonce encontrado" in response:
            for line in response.split('\n'):
                if "Nonce encontrado" in line:
                    try:
                        nonce_str = line.split('(')[1].split(')')[0]
                        nonce = int(nonce_str, 16)
                        
                        elapsed = time.time() - start
                        if elapsed > 0:
                            hashrate = nonce / elapsed
                            print(f"⚡ Hashrate Estimado: {hashrate/1000:.2f} KH/s (Nonce: {nonce} em {elapsed:.1f}s)")
                        
                        return nonce
                    except:
                        continue
    
    return None

def main():
    print("=== Bitcoin FPGA Miner - Stratum Proxy ===")
    print(f"Pool: {POOL_HOST}:{POOL_PORT}")
    print(f"Worker: {POOL_USER}")
    if DEMO_MODE:
        print("Modo: TESTE/DEMO TURBO (target MUITO facilitado, pool quase sempre rejeita shares)")
    else:
        print("Modo: TARGET REAL da pool (shares reais, porém raros!)")
    print()
    
    global current_difficulty

    pool_sock = None
    uart = serial.Serial(UART_PORT, UART_BAUD, timeout=1)
    time.sleep(2)
    
    extranonce1 = ""
    extranonce2_size = 0
    share_counter = 0
    reconnect_delay = 5
    
    print("Aguardando jobs da pool...\n")
    
    buffer = ""
    while True:
        try:
            if pool_sock is None:
                pool_sock = connect_pool()
                if pool_sock is None:
                    print(f"Falha na conexão. Tentando novamente em {reconnect_delay}s...")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 60)
                    continue
                else:
                    reconnect_delay = 5
                    buffer = ""
            
            data = pool_sock.recv(4096).decode()
            if not data:
                print("Pool fechou a conexão. Reconectando...")
                pool_sock.close()
                pool_sock = None
                continue
            
            buffer += data
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if not line.strip():
                    continue
                debug_print("RECV line:", line)

                msg = json.loads(line)
                
                if msg.get("id") == 1 and "result" in msg:
                    extranonce1 = msg["result"][1]
                    extranonce2_size = msg["result"][2]
                    print(f"✓ Conectado: extranonce1={extranonce1}")
                
                elif msg.get("id") == 2:
                    if msg.get("result"):
                        print("✓ Autorizado na pool!\n")
                    else:
                        print(f"✗ Erro de autorização: {msg}")
                
                elif msg.get("id") == 4:
                    if msg.get("result") == True:
                        print("🎉 *** SHARE ACEITO PELA POOL! *** 🎉\n")
                    elif msg.get("error"):
                        error = msg.get("error")
                        print(f"✗ Share rejeitado pela pool: {error}\n")

                # Atualização de dificuldade de share enviada pela pool
                elif msg.get("method") == "mining.set_difficulty":
                    params = msg.get("params", [])
                    if params:
                        try:
                            current_difficulty = float(params[0])
                            print(f"➜ Dificuldade de share atual: {current_difficulty}")
                        except Exception:
                            pass
                
                elif msg.get("method") == "mining.notify":
                    params = msg["params"]
                    job_id = params[0]
                    prevhash = params[1]
                    coinb1 = params[2]
                    coinb2 = params[3]
                    merkle_branches = params[4]
                    version = params[5]
                    nbits = params[6]
                    ntime = params[7]
                    
                    print(f"\n=== Job {job_id} ===")
                    
                    share_counter += 1
                    extranonce2 = f"{share_counter:0{extranonce2_size*2}x}"[-extranonce2_size*2:]
                    print(f"Extranonce2: {extranonce2}")
                    
                    coinbase = coinb1 + extranonce1 + extranonce2 + coinb2
                    merkle_root = calculate_merkle_root(coinbase, merkle_branches)
                    header_hex = build_header_hex(version, prevhash, merkle_root, ntime, nbits)

                    # Escolhe o target:
                    # - REAL: usa dificuldade de share (mining.set_difficulty)
                    # - DEMO: usa target derivado de nbits com facilitação
                    if DEMO_MODE:
                        target_words = bits_to_target(nbits)
                        print("Target DEMO configurado (facilitado).")
                    else:
                        target_words = difficulty_to_target_words(current_difficulty)
                        print(f"Target REAL configurado a partir da dificuldade de share {current_difficulty}.")
                    
                    send_job_to_fpga(uart, header_hex, target_words)
                    
                    # Tempo máximo esperando resultado deste job na FPGA (segundos)
                    nonce = wait_for_result(uart, timeout=60)
                    
                    if nonce is not None:
                        print(f"\n*** SHARE ENCONTRADO! Nonce: {nonce:08x} ***")
                        
                        submit = {
                            "id": 4,
                            "method": "mining.submit",
                            "params": [POOL_USER, job_id, extranonce2, ntime, f"{nonce:08x}"]
                        }
                        debug_print("SEND submit:", submit)
                        pool_sock.send((json.dumps(submit) + "\n").encode())
                        print("📤 Submetido à pool...")
                    else:
                        print("Timeout. Próximo job...\n")
        
        except json.JSONDecodeError:
            continue
        except KeyboardInterrupt:
            print("\n\nEncerrando...")
            if pool_sock:
                pool_sock.close()
            break
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            print(f"Erro de conexão: {e}")
            print("Reconectando em 5 segundos...")
            if pool_sock:
                pool_sock.close()
            pool_sock = None
            time.sleep(5)
        except Exception as e:
            print(f"Erro inesperado: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()