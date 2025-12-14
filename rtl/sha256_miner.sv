`timescale 1ns/1ps

// Minerador simples baseado em SHA-256
// OBS: isto é um "miner" genérico de SHA-256,
//      não implementa o protocolo completo do Bitcoin.
//      Ele recebe um bloco-base de 512 bits, substitui os
//      32 bits menos significativos por um nonce e procura
//      um hash <= target.

module sha256_miner (
    input  logic         clk,
    input  logic         rst,

    // Controle
    input  logic         start,       // pulso para iniciar mineração
    input  logic [511:0] base_block,  // bloco base (sem nonce nos 32 LSB)
    input  logic [255:0] target,      // alvo de dificuldade (quanto menor, mais difícil)

    output logic         busy,        // 1 enquanto estiver minerando
    output logic         found,       // 1 quando encontrar um nonce válido
    output logic [31:0]  found_nonce, // nonce encontrado
    output logic [255:0] found_hash   // hash correspondente
);

    // ==========================
    // Instância do núcleo SHA-256
    // ==========================
    logic         core_start;
    logic         core_done;
    logic [511:0] core_block;
    logic [255:0] core_hash;

    // Bloco usado pelo core: base_block com nonce nos 32 bits LSB
    assign core_block = {base_block[511:32], nonce};

    sha256_core u_core (
        .clk   (clk),
        .rst   (rst),
        .start (core_start),
        .block (core_block),
        .done  (core_done),
        .hash  (core_hash),
        .use_iv(1'b0),
        .iv_in (256'd0)
    );

    // ==========================
    // FSM do minerador
    // ==========================
    typedef enum logic [1:0] {
        M_IDLE,
        M_START_CORE,
        M_WAIT_DONE,
        M_CHECK
    } m_state_t;

    m_state_t state, next_state;
    logic [31:0] nonce;

    // Sequencial
    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            state       <= M_IDLE;
            nonce       <= 32'd0;
            busy        <= 1'b0;
            found       <= 1'b0;
            found_nonce <= 32'd0;
            found_hash  <= 256'd0;
        end else begin
            state <= next_state;

            case (state)
                M_IDLE: begin
                    if (start) begin
                        // Inicia mineração
                        nonce <= 32'd0;
                        busy  <= 1'b1;
                        found <= 1'b0; // limpa flag de encontrado
                    end
                end

                M_WAIT_DONE: begin
                    // Nada sequencial aqui; apenas esperamos core_done
                end

                M_CHECK: begin
                    if (core_hash <= target) begin
                        // Achou solução
                        busy        <= 1'b0;
                        found       <= 1'b1;
                        found_nonce <= nonce;
                        found_hash  <= core_hash;
                    end else begin
                        // Tenta próximo nonce
                        nonce <= nonce + 32'd1;
                    end
                end

                default: ;
            endcase
        end
    end

    // Combinacional: próximo estado e start do núcleo
    always_comb begin
        next_state = state;
        core_start = 1'b0;

        case (state)
            M_IDLE: begin
                if (start)
                    next_state = M_START_CORE;
            end

            M_START_CORE: begin
                // Um ciclo de start para o core
                core_start = 1'b1;
                next_state = M_WAIT_DONE;
            end

            M_WAIT_DONE: begin
                if (core_done)
                    next_state = M_CHECK;
            end

            M_CHECK: begin
                if (core_hash <= target)
                    // Encontrou solução, volta para IDLE aguardando novo start
                    next_state = M_IDLE;
                else
                    // Tenta próximo nonce
                    next_state = M_START_CORE;
            end

            default: next_state = M_IDLE;
        endcase
    end

endmodule
