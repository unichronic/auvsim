// Board-level ForgeFPGA shell for the byte-exact DDS core.
//
// This is the smallest hardware-facing wrapper for a Shrike/Shrike-Lite
// resource check: the board's 50 MHz oscillator is divided by five to make
// the 10 MS/s DAC update enable used by the bench, and the eight DAC bits are
// exposed as GPIO outputs. FTW is fixed here deliberately; the eventual MCU
// or software-plugin control path belongs in a separate interface module.

(* top *) module shrike_dds_top #(
    parameter [31:0] FTW = 32'h028F5C29,
    parameter LUT_FILE = "sim3_gateware/qlut.hex"
)(
    (* iopad_external_pin, clkbuf_inhibit *) input  wire       clk,
    (* iopad_external_pin *) input  wire       reset_n,
    (* iopad_external_pin *) output wire       clk_en,
    (* iopad_external_pin *) output wire [7:0] dac,
    (* iopad_external_pin *) output wire [7:0] dac_oe
);
    reg [2:0] sample_div;
    wire      sample_en = (sample_div == 3'd4);

    assign clk_en = 1'b1;
    assign dac_oe = 8'hff;

    always @(posedge clk or negedge reset_n) begin
        if (!reset_n)
            sample_div <= 3'd0;
        else if (sample_en)
            sample_div <= 3'd0;
        else
            sample_div <= sample_div + 3'd1;
    end

    dds #(.LUT_FILE(LUT_FILE)) u_dds (
        .clk  (clk),
        .rst_n(reset_n),
        .en   (sample_en),
        .ftw  (FTW),
        .dac  (dac)
    );
endmodule
