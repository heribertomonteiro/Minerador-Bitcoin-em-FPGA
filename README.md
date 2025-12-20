# EmbarcaMiner – Bitcoin SHA-256 Miner em FPGA com LiteX

Projeto educacional e experimental de um **minerador Bitcoin simplificado em FPGA**, integrado a um **SoC RISC-V (LiteX)**, com controle via **UART**, **engine SHA-256 em hardware**, e **proxy Stratum em Python** para conexão com pools públicas.

> **Aviso importante**  
> Este projeto **NÃO tem objetivo de mineração lucrativa**.  
> Ele foi desenvolvido para fins **didáticos, acadêmicos e de pesquisa**, explorando:
> - Arquitetura de SoC em FPGA  
> - Implementação de SHA-256 em hardware  
> - Integração HW/SW  
> - Comunicação com pools Bitcoin via Stratum  

---

### Visão Geral da Arquitetura

```
┌────────────────────┐
│ Pool Bitcoin       │
│ (Stratum TCP)      │
└─────────┬──────────┘
          │
          ▼
┌─────────────────────────────┐
│ Proxy Stratum (Python)      │
│ - subscribe / authorize     │
│ - mining.notify             │
│ - build header + target     │
│ - submit shares             │
│ - cálculo de hashrate local │
└─────────┬───────────────────┘
          │ UART
          ▼
┌─────────────────────────────┐
│ SoC LiteX (RISC-V)          │
│ - Console interativo        │
│ - CSRs do minerador         │
│ - Comandos via UART         │
└─────────┬───────────────────┘
          │ CSRs
          ▼
┌─────────────────────────────┐
│ Minerador Bitcoin (FPGA)    │
│ - Double SHA-256            │
│ - FSM de mineração          │
│ - Comparação com target     │
│ - Busca por nonce           │
└─────────────────────────────┘
```
---

##  Módulos do Projeto

### Firmware C (SoC LiteX – RISC-V)

Arquivo principal em C responsável por:

- Interface de console via UART
- Comunicação com o periférico `btcminer` via CSRs
- Carga de jobs (header + target)
- Comandos de controle e debug

#### Comandos disponíveis no console

1. help - lista comandos
2. reboot - reinicia o CPU
3. miner_start - inicia mineração de teste
4. miner_status - mostra status, nonce e hash
5. miner_auto - minera até encontrar nonce
6. miner_target_easy - job extremamente fácil (demo)
7. miner_job <hex_data> - carrega job real da pool
8. miner_clear - limpa estado do minerador

---

###  Módulo `bitcoin_miner` (Verilog)

Engine principal de mineração:

- Recebe:
  - `block0` (512 bits)
  - `block1_tmpl` (512 bits, nonce nos 32 LSB)
  - `target` (256 bits)
- Executa **double SHA-256**
- Varre o espaço de nonces
- Sinaliza quando encontra `hash <= target`

Estados principais:
- `IDLE`
- `PREP`
- `WAIT_HASH`
- `CHECK`

---

###  `sha256_core` (Verilog)

Implementação completa do **SHA-256** em hardware:

- 64 rounds
- Message schedule (`W[0..63]`)
- Constantes K embutidas
- Suporte a:
  - IV padrão
  - IV customizado (encadeamento multi-bloco)

FSM interna:
- `IDLE`
- `LOAD`
- `INIT`
- `ROUND`
- `FINAL`
- `DONE`

---

### `sha256_double` (Verilog)

Responsável por calcular:

Fluxo:
1. SHA do bloco 0
2. SHA do bloco 1 (usando midstate)
3. Segundo SHA sobre o hash resultante

---

### Proxy Stratum (Python)

Script que conecta o FPGA a uma **pool Bitcoin real**.

#### Funcionalidades

- Implementa protocolo Stratum:
  - `mining.subscribe`
  - `mining.authorize`
  - `mining.notify`
  - `mining.submit`
- Monta:
  - Coinbase
  - Merkle root
  - Header Bitcoin
- Envia jobs ao FPGA via UART
- Recebe nonce encontrado
- Submete shares à pool
- **Calcula e exibe a estimativa do hashrate local**

---

## Modos de Operação

### MODO TESTE

- Difficulty forçada (target extremamente fácil)
- Envia **1 share forçado** para aparecer no dashboard da pool
- Ideal para:
  - Testes
  - Demonstração
  - Debug
  - Medição de hashrate local

---

### MODO REAL

- Usa difficulty real enviada pela pool
- Submete apenas shares válidos
- Pode demorar muito para encontrar um nonce (esperado)


---

## Hashrate Local

O hashrate exibido é:

- **Local**
- **Calculado no host (Python)**
- Baseado em:
  - Tempo de execução
  - Quantidade estimada de nonces testados

Exemplo de saída:

> A pool **não utiliza esse hashrate**.  
> O dashboard da pool estima hashrate **apenas com base em shares**.

---

## Requisitos

### Hardware
- FPGA compatível com LiteX
- UART conectada ao host
- Clock estável para o core SHA-256

### Software
- Bibliotecas Python:
  - `pyserial`
  - `hashlib`
- Toolchain LiteX (para SoC)
- GNU Toolchain RISC-V (para firmware)

---

##  Limitações Conhecidas

- Apenas 1 pipeline SHA-256
- Hashrate muito baixo para mineração real
- Hashrate local é estimado (firmware ainda não envia contador real)

---

## Próximos Passos Possíveis

- Contador real de hashes no hardware
- Pipeline SHA-256 (várias rodadas em paralelo)
- Clock mais alto no core
- DMA ou FIFO para jobs
- Dashboard local
- Suporte a múltiplos nonces por job

---
