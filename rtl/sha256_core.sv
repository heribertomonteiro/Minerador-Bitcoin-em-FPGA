module sha256_core (
    input  logic         clk,
    input  logic         rst,
    input  logic         start,
    input  logic [511:0] block,
    output logic         done,
    output logic [255:0] hash,
    // Controle para encadeamento (multi-bloco)
    input  logic         use_iv,      // 0 = usar constantes padrão, 1 = usar iv_in
    input  logic [255:0] iv_in        // {a0,b0,c0,d0,e0,f0,g0,h0}
);

    typedef enum logic [2:0] {
        IDLE, LOAD, INIT, ROUND, FINAL, DONE_STATE
    } state_t;

    state_t state, next_state;
    logic [5:0] round;

    logic [31:0] a,b,c,d,e,f,g,h;
    // Estado inicial usado neste bloco (para somar no FINAL)
    logic [31:0] iv_a,iv_b,iv_c,iv_d,iv_e,iv_f,iv_g,iv_h;
    logic [31:0] W [0:63];
    logic [31:0] T1, T2;
    logic [31:0] Wt;   // palavra W usada na rodada atual

    // ==========================
    // Constantes K
    // ==========================
    logic [31:0] K [0:63];

    integer ki;
    initial begin
        K[ 0] = 32'h428a2f98; K[ 1] = 32'h71374491;
        K[ 2] = 32'hb5c0fbcf; K[ 3] = 32'he9b5dba5;
        K[ 4] = 32'h3956c25b; K[ 5] = 32'h59f111f1;
        K[ 6] = 32'h923f82a4; K[ 7] = 32'hab1c5ed5;
        K[ 8] = 32'hd807aa98; K[ 9] = 32'h12835b01;
        K[10] = 32'h243185be; K[11] = 32'h550c7dc3;
        K[12] = 32'h72be5d74; K[13] = 32'h80deb1fe;
        K[14] = 32'h9bdc06a7; K[15] = 32'hc19bf174;
        K[16] = 32'he49b69c1; K[17] = 32'hefbe4786;
        K[18] = 32'h0fc19dc6; K[19] = 32'h240ca1cc;
        K[20] = 32'h2de92c6f; K[21] = 32'h4a7484aa;
        K[22] = 32'h5cb0a9dc; K[23] = 32'h76f988da;
        K[24] = 32'h983e5152; K[25] = 32'ha831c66d;
        K[26] = 32'hb00327c8; K[27] = 32'hbf597fc7;
        K[28] = 32'hc6e00bf3; K[29] = 32'hd5a79147;
        K[30] = 32'h06ca6351; K[31] = 32'h14292967;
        K[32] = 32'h27b70a85; K[33] = 32'h2e1b2138;
        K[34] = 32'h4d2c6dfc; K[35] = 32'h53380d13;
        K[36] = 32'h650a7354; K[37] = 32'h766a0abb;
        K[38] = 32'h81c2c92e; K[39] = 32'h92722c85;
        K[40] = 32'ha2bfe8a1; K[41] = 32'ha81a664b;
        K[42] = 32'hc24b8b70; K[43] = 32'hc76c51a3;
        K[44] = 32'hd192e819; K[45] = 32'hd6990624;
        K[46] = 32'hf40e3585; K[47] = 32'h106aa070;
        K[48] = 32'h19a4c116; K[49] = 32'h1e376c08;
        K[50] = 32'h2748774c; K[51] = 32'h34b0bcb5;
        K[52] = 32'h391c0cb3; K[53] = 32'h4ed8aa4a;
        K[54] = 32'h5b9cca4f; K[55] = 32'h682e6ff3;
        K[56] = 32'h748f82ee; K[57] = 32'h78a5636f;
        K[58] = 32'h84c87814; K[59] = 32'h8cc70208;
        K[60] = 32'h90befffa; K[61] = 32'ha4506ceb;
        K[62] = 32'hbef9a3f7; K[63] = 32'hc67178f2;
    end

    // ==========================
    // Funções
    // ==========================
    function automatic logic [31:0] ROTR(input logic [31:0] x, input int n);
        ROTR = (x >> n) | (x << (32-n));
    endfunction

    function automatic logic [31:0] Ch (input logic [31:0] x,y,z);
        Ch = (x & y) ^ (~x & z);
    endfunction

    function automatic logic [31:0] Maj(input logic [31:0] x,y,z);
        Maj = (x & y) ^ (x & z) ^ (y & z);
    endfunction

    function automatic logic [31:0] SIG0(input logic [31:0] x);
        SIG0 = ROTR(x,2) ^ ROTR(x,13) ^ ROTR(x,22);
    endfunction

    function automatic logic [31:0] SIG1(input logic [31:0] x);
        SIG1 = ROTR(x,6) ^ ROTR(x,11) ^ ROTR(x,25);
    endfunction

    function automatic logic [31:0] sig0(input logic [31:0] x);
        sig0 = ROTR(x,7) ^ ROTR(x,18) ^ (x >> 3);
    endfunction

    function automatic logic [31:0] sig1(input logic [31:0] x);
        sig1 = ROTR(x,17) ^ ROTR(x,19) ^ (x >> 10);
    endfunction

    // ==========================
    // FSM sequencial
    // ==========================
    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= IDLE;
            round <= 0;
            done  <= 0;
            iv_a  <= 32'd0; iv_b <= 32'd0; iv_c <= 32'd0; iv_d <= 32'd0;
            iv_e  <= 32'd0; iv_f <= 32'd0; iv_g <= 32'd0; iv_h <= 32'd0;
        end else begin
            state <= next_state;

            if (state == ROUND)
                round <= round + 1;
            else
                round <= 0;

            done <= (state == DONE_STATE);
        end
    end

    // ==========================
    // FSM combinacional
    // ==========================
    always_comb begin
        next_state = state;

        case (state)
            IDLE:       if (start) next_state = LOAD;
            LOAD:       next_state = INIT;
            INIT:       next_state = ROUND;
            ROUND:      if (round == 63) next_state = FINAL;
            FINAL:      next_state = DONE_STATE;
            DONE_STATE: if (!start) next_state = IDLE;
        endcase
    end

    // ==========================
    // Datapath
    // ==========================
    integer i;

    // Palavra de mensagem usada na rodada atual (com agenda correta de W)
    always_comb begin
        if (round < 16)
            Wt = W[round];
        else
            Wt = sig1(W[round-2]) + W[round-7]
               + sig0(W[round-15]) + W[round-16];
    end

    always_ff @(posedge clk) begin
        case (state)
            LOAD: begin
                for (i = 0; i < 16; i++)
                    W[i] <= block[511 - i*32 -: 32];
                for (i = 16; i < 64; i++)
                    W[i] <= 0;
            end

            INIT: begin
                if (use_iv) begin
                    {a,b,c,d,e,f,g,h}   <= iv_in;
                    {iv_a,iv_b,iv_c,iv_d,
                     iv_e,iv_f,iv_g,iv_h} <= iv_in;
                end else begin
                    a <= 32'h6a09e667; b <= 32'hbb67ae85;
                    c <= 32'h3c6ef372; d <= 32'ha54ff53a;
                    e <= 32'h510e527f; f <= 32'h9b05688c;
                    g <= 32'h1f83d9ab; h <= 32'h5be0cd19;

                    iv_a <= 32'h6a09e667; iv_b <= 32'hbb67ae85;
                    iv_c <= 32'h3c6ef372; iv_d <= 32'ha54ff53a;
                    iv_e <= 32'h510e527f; iv_f <= 32'h9b05688c;
                    iv_g <= 32'h1f83d9ab; iv_h <= 32'h5be0cd19;
                end
            end

            ROUND: begin
                // Atualiza W[round] para t >= 16 e usa sempre Wt na rodada
                if (round >= 16)
                    W[round] <= Wt;

                T1 = h + SIG1(e) + Ch(e,f,g) + K[round] + Wt;
                T2 = SIG0(a) + Maj(a,b,c);

                h <= g; g <= f; f <= e;
                e <= d + T1;
                d <= c; c <= b; b <= a;
                a <= T1 + T2;
            end

            FINAL: begin
                hash <= {
                    a + iv_a, b + iv_b,
                    c + iv_c, d + iv_d,
                    e + iv_e, f + iv_f,
                    g + iv_g, h + iv_h
                };
            end
        endcase
    end

endmodule
