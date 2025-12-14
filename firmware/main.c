#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include <irq.h>
#include <uart.h>
#include <console.h>
#include <generated/csr.h>

#define VEC_SIZE 8

static char *readstr(void)
{
    char c[2];
    static char s[64];
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
}

static void reboot(void)
{
    ctrl_reset_write(1);
}

static void toggle_led(void)
{
    int i;
    printf("invertendo led...\n");
    #ifdef CSR_LEDS_OUT_ADDR
    i = leds_out_read();
    leds_out_write(!i);
    #else
    printf("LED CSR nao disponivel neste SoC.\n");
    #endif
}

// -------------------------
// Controle simples do miner
// -------------------------

static void miner_load_simple_job(void)
{
    // Job de teste: header todo zero, target maximo (qualquer hash serve).
    // Nao eh um bloco Bitcoin real, mas exercita o hardware.

    // block0[0..15] = 0
    btcminer_block0_0_write(0);
    btcminer_block0_1_write(0);
    btcminer_block0_2_write(0);
    btcminer_block0_3_write(0);
    btcminer_block0_4_write(0);
    btcminer_block0_5_write(0);
    btcminer_block0_6_write(0);
    btcminer_block0_7_write(0);
    btcminer_block0_8_write(0);
    btcminer_block0_9_write(0);
    btcminer_block0_10_write(0);
    btcminer_block0_11_write(0);
    btcminer_block0_12_write(0);
    btcminer_block0_13_write(0);
    btcminer_block0_14_write(0);
    btcminer_block0_15_write(0);

    // block1_tmpl[0..15] = 0 (nonce sera sobrescrito pelo minerador)
    btcminer_block1_0_write(0);
    btcminer_block1_1_write(0);
    btcminer_block1_2_write(0);
    btcminer_block1_3_write(0);
    btcminer_block1_4_write(0);
    btcminer_block1_5_write(0);
    btcminer_block1_6_write(0);
    btcminer_block1_7_write(0);
    btcminer_block1_8_write(0);
    btcminer_block1_9_write(0);
    btcminer_block1_10_write(0);
    btcminer_block1_11_write(0);
    btcminer_block1_12_write(0);
    btcminer_block1_13_write(0);
    btcminer_block1_14_write(0);
    btcminer_block1_15_write(0);

    // target = 0xFFFF...FFFF (dificuldade minima)
    btcminer_target_0_write(0xFFFFFFFF);
    btcminer_target_1_write(0xFFFFFFFF);
    btcminer_target_2_write(0xFFFFFFFF);
    btcminer_target_3_write(0xFFFFFFFF);
    btcminer_target_4_write(0xFFFFFFFF);
    btcminer_target_5_write(0xFFFFFFFF);
    btcminer_target_6_write(0xFFFFFFFF);
    btcminer_target_7_write(0xFFFFFFFF);
}

static void miner_start_cmd(void)
{
    printf("Configurando job de teste no minerador...\n");
    miner_load_simple_job();

    printf("Disparando mineracao (nonce inicial = 0)...\n");
    btcminer_start_write(1);
}

static void miner_status_cmd(void)
{
    unsigned int st;
    int busy, found;
    uint32_t nonce;
    uint32_t h[8];

    st    = btcminer_status_read();
    busy  =  st        & 0x1;
    found = (st >> 1)  & 0x1;

    printf("miner: busy=%d, found=%d\n", busy, found);

#ifdef CSR_LEDS_OUT_ADDR
    // Liga LEDs externos: bit0 = busy, bit7 = found
    leds_out_write((busy ? 0x01 : 0x00) | (found ? 0x80 : 0x00));
#endif

    if (!found)
        return;

    nonce = btcminer_found_nonce_read();
    h[0]  = btcminer_found_hash_0_read();
    h[1]  = btcminer_found_hash_1_read();
    h[2]  = btcminer_found_hash_2_read();
    h[3]  = btcminer_found_hash_3_read();
    h[4]  = btcminer_found_hash_4_read();
    h[5]  = btcminer_found_hash_5_read();
    h[6]  = btcminer_found_hash_6_read();
    h[7]  = btcminer_found_hash_7_read();

    printf("nonce encontrado = %u (0x%08x)\n", nonce, nonce);
    printf("hash encontrado = ");
    // Imprime em ordem "mais humana" (palavra alta primeiro)
    printf("%08x%08x%08x%08x%08x%08x%08x%08x\n",
        h[7], h[6], h[5], h[4], h[3], h[2], h[1], h[0]);
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
    else if(strcmp(token, "led") == 0)
        toggle_led();
    else if(strcmp(token, "miner_start") == 0)
        miner_start_cmd();
    else if(strcmp(token, "miner_status") == 0)
        miner_status_cmd();
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
