#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include <irq.h>
#include <uart.h>
#include <console.h>
#include <generated/csr.h>
#include <hw/common.h>   // csr_write_simple / csr_read_simple

#define VEC_SIZE 8

// Índice base em palavras de 32 bits para o periférico btcminer.
// OBS: offsets abaixo são apenas referência; usamos as funções geradas em csr.h.
#define BTCMINER_BASE_WORD   CSR_BTCMINER_BASE
#define OFS_START        0
#define OFS_BLOCK0_0     1
#define OFS_BLOCK1_0     17
#define OFS_TARGET_0     33
#define OFS_STATUS       41
#define OFS_FOUND_NONCE  42
#define OFS_FOUND_HASH_0 43

static inline void btcminer_start_pulse(void)
{
    btcminer_start_write(1);
}

static inline uint32_t btcminer_status_read_simple(void)
{
    return btcminer_status_read();
}

static inline uint32_t btcminer_found_nonce_read_simple(void)
{
    return btcminer_found_nonce_read();
}

// Agora usamos as funções reais geradas em csr.h para cada word do hash.
static inline uint32_t btcminer_found_hash_read_simple(int idx)
{
    switch (idx) {
    case 0: return btcminer_found_hash_0_read();
    case 1: return btcminer_found_hash_1_read();
    case 2: return btcminer_found_hash_2_read();
    case 3: return btcminer_found_hash_3_read();
    case 4: return btcminer_found_hash_4_read();
    case 5: return btcminer_found_hash_5_read();
    case 6: return btcminer_found_hash_6_read();
    case 7: return btcminer_found_hash_7_read();
    default: return 0;
    }
}

// Helpers para escrever block0/block1/target via CSRs gerados.
static inline void btcminer_block0_write(int idx, uint32_t v)
{
    switch (idx) {
    case 0:  btcminer_block0_0_write(v);  break;
    case 1:  btcminer_block0_1_write(v);  break;
    case 2:  btcminer_block0_2_write(v);  break;
    case 3:  btcminer_block0_3_write(v);  break;
    case 4:  btcminer_block0_4_write(v);  break;
    case 5:  btcminer_block0_5_write(v);  break;
    case 6:  btcminer_block0_6_write(v);  break;
    case 7:  btcminer_block0_7_write(v);  break;
    case 8:  btcminer_block0_8_write(v);  break;
    case 9:  btcminer_block0_9_write(v);  break;
    case 10: btcminer_block0_10_write(v); break;
    case 11: btcminer_block0_11_write(v); break;
    case 12: btcminer_block0_12_write(v); break;
    case 13: btcminer_block0_13_write(v); break;
    case 14: btcminer_block0_14_write(v); break;
    case 15: btcminer_block0_15_write(v); break;
    default: break;
    }
}

static inline void btcminer_block1_write(int idx, uint32_t v)
{
    switch (idx) {
    case 0:  btcminer_block1_0_write(v);  break;
    case 1:  btcminer_block1_1_write(v);  break;
    case 2:  btcminer_block1_2_write(v);  break;
    case 3:  btcminer_block1_3_write(v);  break;
    case 4:  btcminer_block1_4_write(v);  break;
    case 5:  btcminer_block1_5_write(v);  break;
    case 6:  btcminer_block1_6_write(v);  break;
    case 7:  btcminer_block1_7_write(v);  break;
    case 8:  btcminer_block1_8_write(v);  break;
    case 9:  btcminer_block1_9_write(v);  break;
    case 10: btcminer_block1_10_write(v); break;
    case 11: btcminer_block1_11_write(v); break;
    case 12: btcminer_block1_12_write(v); break;
    case 13: btcminer_block1_13_write(v); break;
    case 14: btcminer_block1_14_write(v); break;
    case 15: btcminer_block1_15_write(v); break;
    default: break;
    }
}

static inline void btcminer_target_write(int idx, uint32_t v)
{
    switch (idx) {
    case 0: btcminer_target_0_write(v); break;
    case 1: btcminer_target_1_write(v); break;
    case 2: btcminer_target_2_write(v); break;
    case 3: btcminer_target_3_write(v); break;
    case 4: btcminer_target_4_write(v); break;
    case 5: btcminer_target_5_write(v); break;
    case 6: btcminer_target_6_write(v); break;
    case 7: btcminer_target_7_write(v); break;
    default: break;
    }
}

static char *readstr(void)
{
    char c[2];
    static char s[512];  // Aumentado de 64 para 512 para receber job completo
    static int ptr = 0;

    if(readchar_nonblock()) {
        c[0] = readchar();
        c[1] = 0;
        switch(c[0]) {
            case 0x7f:
            case 0x08:
                if(ptr > 0) {
                    ptr--;
                    putsnonl("\x08 \x08");
                }
                break;
            case 0x07:
                break;
            case '\r':
            case '\n':
                s[ptr] = 0x00;
                putsnonl("\n");
                ptr = 0;
                return s;
            default:
                if(ptr >= (sizeof(s) - 1))
                    break;
                putsnonl(c);
                s[ptr] = c[0];
                ptr++;
                break;
        }
    }
    return NULL;
}

static char *get_token(char **str)
{
    char *c, *d;

    c = (char *)strchr(*str, ' ');
    if(c == NULL) {
        d = *str;
        *str = *str+strlen(*str);
        return d;
    }
    *c = 0;
    d = *str;
    *str = c+1;
    return d;
}

static void prompt(void)
{
    printf("RUNTIME>");
}

static void help(void)
{
    puts("Available commands:");
    puts("help                            - this command");
    puts("reboot                          - reboot CPU");
    puts("led                             - led test");
    puts("miner_start                     - inicia mineracao de teste");
    puts("miner_status                    - mostra status/resultado do minerador");
    puts("miner_auto                      - inicia mineracao e espera ate encontrar nonce");
    puts("miner_target_easy               - carrega job facil de demonstracao e inicia mineracao");
    puts("miner_job <hex_data>            - carrega job da pool (80 bytes header + 32 bytes target em hex)");
    puts("miner_clear                     - limpa resultado anterior");
}

static void reboot(void)
{
    ctrl_reset_write(1);
}


// -------------------------
// Controle simples do miner
// -------------------------

// Job de teste "realista" com target difícil (para simular um bloco verdadeiro)
static void miner_load_simple_job(void)
{
    int i;

    printf("Carregando job de teste REALISTA (header nao-zero, target dificil)...\n");

    // Exemplo de header "realista" simplificado:
    // block0[0] = versao (0x20000000)
    // block0[1..7] = parte do prev_hash (fake aqui)
    // block0[8..15] = parte do merkle_root (fake aqui)
    btcminer_block0_write(0, 0x20000000); // version
    btcminer_block0_write(1, 0x11223344);
    btcminer_block0_write(2, 0x55667788);
    btcminer_block0_write(3, 0x99AABBCC);
    btcminer_block0_write(4, 0xDDEEFF00);
    btcminer_block0_write(5, 0x0F1E2D3C);
    btcminer_block0_write(6, 0x4B5A6978);
    btcminer_block0_write(7, 0x8796A5B4);
    btcminer_block0_write(8, 0xC3D2E1F0);
    btcminer_block0_write(9, 0x01020304);
    btcminer_block0_write(10, 0x05060708);
    btcminer_block0_write(11, 0x090A0B0C);
    btcminer_block0_write(12, 0x0D0E0F10);
    btcminer_block0_write(13, 0x11121314);
    btcminer_block0_write(14, 0x15161718);
    btcminer_block0_write(15, 0x191A1B1C);

    // block1:
    // word 0: timestamp
    // word 1: bits (dificuldade codificada)
    // word 2: nonce (SERÁ substituído pelo hardware)
    // resto: padding/zeros para este exemplo
    btcminer_block1_write(0, 0x5E2A5D80); // timestamp ~2020
    btcminer_block1_write(1, 0x1d00ffff); // bits (como em blocos iniciais de Bitcoin)
    btcminer_block1_write(2, 0x00000000); // nonce (será variado pelo miner)
    for (i = 3; i < 16; i++)
        btcminer_block1_write(i, 0x00000000);

    // target ainda dificil (quase tudo 0, ultimo word 0x0000FFFF)
    for (i = 0; i < 7; i++)
        btcminer_target_write(i, 0x00000000);
    btcminer_target_write(7, 0x0000FFFF);
}

// Job de teste BEM FÁCIL para demonstração local (encontrar nonce rápido)
static void miner_load_easy_job(void)
{
    int i;

    printf("Carregando job de teste FACIL (header simples, target MUITO facil)...\n");

    // Header simples: zera tudo
    for (i = 0; i < 16; i++)
        btcminer_block0_write(i, 0x00000000);
    for (i = 0; i < 16; i++)
        btcminer_block1_write(i, 0x00000000);

    // Target extremamente fácil: todos os bits em 1
    // Qualquer hash será < target, então o primeiro nonce
    // que o miner testar já deve satisfazer a condição.
    for (i = 0; i < 8; i++)
        btcminer_target_write(i, 0xFFFFFFFF);
}

// Comando: carrega job fácil e inicia mineração
static void miner_target_easy_cmd(void)
{
    printf("Configurando job FACIL e iniciando mineracao (modo demonstracao)...\n");
    miner_load_easy_job();
    btcminer_start_pulse();
    printf("Job facil iniciado. Use 'miner_status' para verificar quando encontrar nonce.\n");
}

static void miner_start_cmd(void)
{
    printf("Configurando job de teste no minerador...\n");
    miner_load_simple_job();

    printf("Disparando mineracao (nonce inicial = 0)...\n");
    btcminer_start_pulse();

    printf("Comando miner_start enviado. Use 'miner_status' para acompanhar.\n");
}

static void miner_status_cmd(void)
{
    unsigned int st;
    int busy, found;
    uint32_t nonce;
    uint32_t h[8];

    st    = btcminer_status_read_simple();
    busy  =  st        & 0x1;
    found = (st >> 1)  & 0x1;

    printf("Status do minerador: busy=%d, found=%d\n", busy, found);

#ifdef CSR_LEDS_OUT_ADDR
    // Liga LEDs externos: bit0 = busy, bit7 = found
    leds_out_write((busy ? 0x01 : 0x00) | (found ? 0x80 : 0x00));
#endif

    if (!found) {
        printf("Nenhum nonce encontrado ainda. Tente novamente em alguns segundos.\n");
        return;
    }

    nonce = btcminer_found_nonce_read_simple();
    for (int i = 0; i < 8; i++)
        h[i] = btcminer_found_hash_read_simple(i);

    printf("Nonce encontrado = %lu (0x%08lx)\n", (unsigned long)nonce, (unsigned long)nonce);
    printf("Hash encontrado  = ");
    printf("%08lx%08lx%08lx%08lx%08lx%08lx%08lx%08lx\n",
        (unsigned long)h[7], (unsigned long)h[6], (unsigned long)h[5], (unsigned long)h[4],
        (unsigned long)h[3], (unsigned long)h[2], (unsigned long)h[1], (unsigned long)h[0]);
}

// novo comando: inicia e espera até encontrar um nonce, medindo tentativas simples
static void miner_auto_cmd(void)
{
    unsigned int st;
    int busy, found;
    uint32_t loops = 0;

    printf("Iniciando mineracao automatica...\n");
    miner_start_cmd();

    while (1) {
        st    = btcminer_status_read_simple();
        busy  =  st        & 0x1;
        found = (st >> 1)  & 0x1;
        loops++;

        if (found) {
            printf("Mineracao concluida apos %lu leituras de status.\n", (unsigned long)loops);
            miner_status_cmd(); // imprime nonce/hash
            break;
        }

        if (!busy && !found) {
            printf("Minerador parado sem encontrar nonce (algo errado?).\n");
            break;
        }
    }
}

// Converte 2 caracteres hex para byte
static uint8_t hex_to_byte(const char *hex)
{
    uint8_t val = 0;
    for (int i = 0; i < 2; i++) {
        val <<= 4;
        char c = hex[i];
        if (c >= '0' && c <= '9')
            val |= (c - '0');
        else if (c >= 'a' && c <= 'f')
            val |= (c - 'a' + 10);
        else if (c >= 'A' && c <= 'F')
            val |= (c - 'A' + 10);
    }
    return val;
}

// Novo comando para limpar estado (força novo job)
static void miner_clear_cmd(void)
{
    printf("Limpando estado do minerador...\n");
    // Re-escrever o registrador start para resetar o estado interno
    btcminer_start_pulse();
    printf("Estado limpo. Pronto para novo job.\n");
}

// Adicione esta função logo após as includes ou no início do arquivo, antes de miner_job_cmd
static inline uint32_t swap_endian(uint32_t x) {
    return ((x >> 24) & 0xff) |
           ((x >> 8)  & 0xff00) |
           ((x << 8)  & 0xff0000) |
           ((x << 24) & 0xff000000);
}

// Modifique a função miner_job_cmd existente:
static void miner_job_cmd(char *hex_data)
{
    int len = strlen(hex_data);
    // 224 hex chars = 80 bytes header + 32 bytes target
    if (len < 224) {
        printf("Erro: Tamanho insuficiente (%d)\n", len);
        return;
    }

    uint32_t val;

    // --- Processar Header (80 bytes -> 20 words) ---
    for (int i = 0; i < 20; i++) {
        val = 0;
        for (int j = 0; j < 4; j++) {
            // Monta a word invertendo para Big-Endian
            val |= ((uint32_t)hex_to_byte(&hex_data[(i * 8) + (j * 2)])) << (24 - (j * 8));
        }
        
        if (i < 16)
            btcminer_block0_write(i, val);
        else
            btcminer_block1_write(i - 16, val);
    }

    // --- Processar Target (32 bytes -> 8 words) ---
    for (int i = 0; i < 8; i++) {
        val = 0;
        for (int j = 0; j < 4; j++) {
            val |= ((uint32_t)hex_to_byte(&hex_data[160 + (i * 8) + (j * 2)])) << (24 - (j * 8));
        }
        btcminer_target_write(i, val);
    }

    printf("Job carregado corretamente. Minerando...\n");
    btcminer_start_pulse();
}

static void console_service(void) {
    char *str;
    char *token;

    str = readstr();
    if(str == NULL) return;
    token = get_token(&str);
    if(strcmp(token, "help") == 0)
        help();
    else if(strcmp(token, "reboot") == 0)
        reboot();
    else if(strcmp(token, "miner_start") == 0)
        miner_start_cmd();
    else if(strcmp(token, "miner_status") == 0)
        miner_status_cmd();
    else if(strcmp(token, "miner_auto") == 0)
        miner_auto_cmd();
    else if(strcmp(token, "miner_target_easy") == 0)
        miner_target_easy_cmd();
    else if(strcmp(token, "miner_job") == 0)
        miner_job_cmd(str);
    else if(strcmp(token, "miner_clear") == 0)
        miner_clear_cmd();
    prompt();
}

int main(void) {
#ifdef CONFIG_CPU_HAS_INTERRUPT
    irq_setmask(0);
    irq_setie(1);
#endif
    uart_init();

    printf("HelloWorld!\n");
    help();
    prompt();

    while(1) {
        console_service();
    }

    return 0;
}
