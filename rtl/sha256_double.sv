`timescale 1ns/1ps

// Calcula SHA256(SHA256(msg)) de um header em dois blocos de 512 bits.
// Entrada: dois blocos de 512 bits (msg já com padding de 80 bytes, 2 blocos).
// Saída: hash duplo de 256 bits.

module sha256_double (
    input  logic         clk,
    input  logic         rst,
    input  logic         start,      // pulso de início
    input  logic [511:0] block0,     // primeiro bloco (bytes 0..63 do header)
    input  logic [511:0] block1,     // segundo bloco (bytes 64..79 + padding)
    output logic         done,       // 1 por um ciclo quando hash2 pronto
    output logic [255:0] hash2       // SHA256(SHA256(header))
);

    // Estados da FSM interna
    typedef enum logic [2:0] {
        D_IDLE,
        D_START0,
        D_WAIT0,
        D_START1,
        D_WAIT1,
        D_START2,
        D_WAIT2
    } d_state_t;

    d_state_t state, next_state;

    // Conexão com o núcleo sha256_core
    logic         core_start;
    logic         core_done;
    logic [511:0] core_block;
    logic [255:0] core_hash;
    logic         core_use_iv;
    logic [255:0] core_iv_in;

    // Registros internos
    logic [511:0] blk0_reg, blk1_reg;
    logic [255:0] midstate;   // hash após block0
    logic [255:0] hash1;      // hash após block1 (hash do header)

    // Instância do núcleo
    sha256_core u_core (
        .clk   (clk),
        .rst   (rst),
        .start (core_start),
        .block (core_block),
        .done  (core_done),
        .hash  (core_hash),
        .use_iv(core_use_iv),
        .iv_in (core_iv_in)
    );

    // ==========================
    // FSM sequencial
    // ==========================
    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            state    <= D_IDLE;
            blk0_reg <= 512'd0;
            blk1_reg <= 512'd0;
            midstate <= 256'd0;
            hash1    <= 256'd0;
            hash2    <= 256'd0;
            done     <= 1'b0;
        end else begin
            state <= next_state;

            // done é pulso de 1 ciclo ao sair de D_WAIT2
            done <= 1'b0;

            if (state == D_IDLE && start) begin
                blk0_reg <= block0;
                blk1_reg <= block1;
            end

            if (state == D_WAIT0 && core_done) begin
                midstate <= core_hash;
            end

            if (state == D_WAIT1 && core_done) begin
                hash1 <= core_hash;
            end

            if (state == D_WAIT2 && core_done) begin
                hash2 <= core_hash;
                done  <= 1'b1;
            end
        end
    end

    // ==========================
    // Bloco do segundo SHA (a partir de hash1)
    // ==========================
    // Mensagem de 32 bytes (256 bits):
    // W0..W7  = hash1 (8 palavras de 32 bits)
    // W8      = 0x80000000
    // W9..W14 = 0
    // W15     = 256 (comprimento em bits)

    logic [511:0] block2;
    always_comb begin
        block2 = {
            hash1,                // W0..W7
            32'h80000000,         // W8
            32'd0, 32'd0, 32'd0,  // W9..W11
            32'd0, 32'd0, 32'd0,  // W12..W14
            32'd256               // W15
        };
    end

    // ==========================
    // FSM combinacional
    // ==========================
    always_comb begin
        next_state   = state;
        core_start   = 1'b0;
        core_block   = 512'd0;
        core_use_iv  = 1'b0;
        core_iv_in   = 256'd0;

        case (state)
            D_IDLE: begin
                if (start)
                    next_state = D_START0;
            end

            D_START0: begin
                // SHA do primeiro bloco com IV padrão
                core_start  = 1'b1;
                core_block  = blk0_reg;
                core_use_iv = 1'b0;
                next_state  = D_WAIT0;
            end

            D_WAIT0: begin
                core_block  = blk0_reg;
                core_use_iv = 1'b0;
                if (core_done)
                    next_state = D_START1;
            end

            D_START1: begin
                // SHA do segundo bloco com IV = midstate
                core_start  = 1'b1;
                core_block  = blk1_reg;
                core_use_iv = 1'b1;
                core_iv_in  = midstate;
                next_state  = D_WAIT1;
            end

            D_WAIT1: begin
                core_block  = blk1_reg;
                core_use_iv = 1'b1;
                core_iv_in  = midstate;
                if (core_done)
                    next_state = D_START2;
            end

            D_START2: begin
                // Segundo SHA (mensagem = hash1)
                core_start  = 1'b1;
                core_block  = block2;
                core_use_iv = 1'b0;
                next_state  = D_WAIT2;
            end

            D_WAIT2: begin
                core_block  = block2;
                core_use_iv = 1'b0;
                if (core_done)
                    next_state = D_IDLE;
            end

            default: begin
                next_state = D_IDLE;
            end
        endcase
    end

endmodule
