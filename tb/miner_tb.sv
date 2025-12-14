`timescale 1ns/1ps

module miner_tb;

    logic clk;
    logic rst;
    logic start;

    logic [511:0] block0;
    logic [511:0] block1_tmpl;
    logic [255:0] target;

    logic busy;
    logic found;
    logic [31:0]  found_nonce;
    logic [255:0] found_hash;

    bitcoin_miner dut (
        .clk         (clk),
        .rst         (rst),
        .start       (start),
        .block0      (block0),
        .block1_tmpl (block1_tmpl),
        .target      (target),
        .busy        (busy),
        .found       (found),
        .found_nonce (found_nonce),
        .found_hash  (found_hash)
    );

    // Clock 100 MHz
    always #5 clk = ~clk;

    initial begin
        $display("=== BITCOIN MINER TB ===");

        clk   = 0;
        rst   = 1;
        start = 0;

        block0      = 512'd0;
        block1_tmpl = 512'd0;
        // Alvo muito fácil: qualquer hash serve
        target      = 256'hFFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF;

        #20 rst = 0;

        // Para este testbench, usamos blocos artificiais quaisquer.
        // Na aplicação real, block0/block1_tmpl devem vir do header Bitcoin
        // já organizado (big-endian) e com padding correto.
        block0      = 512'h000102030405060708090A0B0C0D0E0F_101112131415161718191A1B1C1D1E1F_202122232425262728292A2B2C2D2E2F_303132333435363738393A3B3C3D3E3F;
        block1_tmpl = 512'h404142434445464748494A4B4C4D4E4F_505152535455565758595A5B5C5D5E5F_606162636465666768696A6B6C6D6E6F_00000000000000000000000000000000;

        #10 start = 1;
        #10 start = 0;

        // Espera até encontrar uma solução (como o alvo é máximo,
        // o primeiro nonce já é aceito).
        wait (found == 1'b1);

        $display("Nonce encontrado: %0d", found_nonce);
        $display("Hash encontrado : %h", found_hash);

        #20;
        $finish;
    end

endmodule
