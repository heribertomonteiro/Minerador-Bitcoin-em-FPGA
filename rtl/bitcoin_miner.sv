`timescale 1ns/1ps

// Minerador Bitcoin simplificado
// - Recebe dois blocos de 512 bits que representam o header (80 bytes) já
//   organizado/padding para SHA-256 (block0: bytes 0..63, block1: bytes 64..79 + padding).
// - Assume que os 32 bits menos significativos de block1 são o campo nonce.
// - Faz double SHA-256 do header variando o nonce e compara com target.
// - Não implementa protocolo de rede/pool, apenas o engine de prova de trabalho.

module bitcoin_miner (
    input  logic         clk,
    input  logic         rst,

    input  logic         start,          // pulso para iniciar mineração
    input  logic [511:0] block0,         // primeiro bloco fixo
    input  logic [511:0] block1_tmpl,    // segundo bloco com nonce nos 32 LSB
    input  logic [255:0] target,         // alvo de dificuldade

    output logic         busy,           // 1 enquanto estiver minerando
    output logic         found,          // 1 quando encontrar um nonce válido
    output logic [31:0]  found_nonce,
    output logic [255:0] found_hash
);

    // ==========================
    // Instância do double SHA-256
    // ==========================
    logic         d_start;
    logic         d_done;
    logic [511:0] d_block0, d_block1;
    logic [255:0] d_hash2;

    sha256_double u_double (
        .clk   (clk),
        .rst   (rst),
        .start (d_start),
        .block0(d_block0),
        .block1(d_block1),
        .done  (d_done),
        .hash2 (d_hash2)
    );

    // ==========================
    // FSM do minerador
    // ==========================
    typedef enum logic [1:0] {
        M_IDLE,
        M_PREP,
        M_WAIT_HASH,
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
                        nonce       <= 32'd0;
                        busy        <= 1'b1;
                        found       <= 1'b0;
                        found_nonce <= 32'd0;
                        found_hash  <= 256'd0;
                    end
                end

                M_CHECK: begin
                    if (d_hash2 <= target) begin
                        busy        <= 1'b0;
                        found       <= 1'b1;
                        found_nonce <= nonce;
                        found_hash  <= d_hash2;
                    end else begin
                        nonce <= nonce + 32'd1;
                    end
                end

                default: ;
            endcase
        end
    end

    // Combinacional: próximo estado e controle do double SHA
    always_comb begin
        next_state = state;
        d_start    = 1'b0;

        case (state)
            M_IDLE: begin
                if (start)
                    next_state = M_PREP;
            end

            M_PREP: begin
                // Um ciclo de start para o double SHA
                d_start    = 1'b1;
                next_state = M_WAIT_HASH;
            end

            M_WAIT_HASH: begin
                if (d_done)
                    next_state = M_CHECK;
            end

            M_CHECK: begin
                if (d_hash2 <= target)
                    next_state = M_IDLE;      // solução encontrada
                else
                    next_state = M_PREP;      // tenta próximo nonce
            end

            default: next_state = M_IDLE;
        endcase
    end

    // Blocos que vão para o double SHA:
    // block0 é fixo; em block1 substituímos os 32 LSB pelo nonce.
    assign d_block0 = block0;
    assign d_block1 = {block1_tmpl[511:32], nonce};

endmodule
