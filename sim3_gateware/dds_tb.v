// Testbench: dump N samples at a fixed tuning word for diffing against SIM-0.
`timescale 1ns/1ps
module dds_tb;
    localparam N = 8192;
    reg clk = 0, rst_n = 0, en = 0;
    reg [31:0] ftw;
    wire [7:0] dac;
    integer f, i;

    dds uut (.clk(clk), .rst_n(rst_n), .en(en), .ftw(ftw), .dac(dac));

    // Waveform dump for gtkwave, opt-in via +vcd so the byte-exact check in
    // sim3_check.py is not slowed by writing a VCD it never reads.
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("dds.vcd");
            $dumpvars(0, dds_tb);
        end
    end
    always #50 clk = ~clk;           // 10 MHz sample clock

    initial begin
        if (!$value$plusargs("ftw=%d", ftw)) ftw = 32'h028F5C29;  // 100 kHz
        f = $fopen("dds_out.txt", "w");
        @(negedge clk); rst_n = 1; en = 1;
        // dac is registered, so the first valid sample appears one clock later
        @(posedge clk);
        for (i = 0; i < N; i = i + 1) begin
            @(posedge clk);
            $fwrite(f, "%0d\n", dac);
        end
        $fclose(f);
        $finish;
    end
endmodule
