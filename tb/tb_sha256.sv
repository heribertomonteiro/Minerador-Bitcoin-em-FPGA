`timescale 1ns/1ps

module tb_sha256;

    logic clk;
    logic rst;
    logic start;
    logic [511:0] block;
    logic done;
    logic [255:0] hash;

    sha256_core dut (
        .clk   (clk),
        .rst   (rst),
        .start (start),
        .block (block),
        .done  (done),
        .hash  (hash),
        .use_iv(1'b0),
        .iv_in (256'd0)
    );

    // Clock 100 MHz
    always #5 clk = ~clk;

    initial begin
        $display("=== SHA-256 TB (iverilog/vvp) ===");

        // Inicialização
        clk   = 0;
        rst   = 1;
        start = 0;
        block = 512'd0;

        // Reset
        #20;
        rst = 0;

        // "abc" + padding (TUDO EM UMA LINHA)
        block = 512'h61626380000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000018;

        // Pulso start
        #10 start = 1;
        #10 start = 0;

        // Aguarda finalizar
        wait (done == 1);

        $display("Hash calculado:");
        $display("%h", hash);

        // Hash esperado (UMA LINHA)
        if (hash == 256'hba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad)
            $display("TESTE PASSOU ✅");
        else
            $display("TESTE FALHOU ❌");

        #20;
        $finish;
    end

endmodule
