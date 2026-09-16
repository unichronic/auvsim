// SIM-3 -- DDS core for the Renesas SLG47910 (ForgeFPGA).
//
// 32-bit phase accumulator -> 12-bit LUT address -> 8-bit DAC code, using a
// quarter-wave-symmetric sine table: 1025 x 8b = 8200 bits = 25% of the
// SLG47910's 32 kb BRAM.  The full 4096 x 8 table would be 32768 bits --
// exactly 100% of BRAM, leaving nothing for anything else -- so the symmetry
// is required, not an optimisation.
//
// The +1 correction on the negative half is NOT cosmetic.  The reference
// table is round(127.5 + 127.5*sin), and floor(-x) != -floor(x), so naive
// negation is one LSB high across all 2047 negative-half entries, which shows
// up as even-order harmonic distortion.  Verified byte-exact against SIM-0.
module dds #(
    parameter PHASE_BITS = 32,
    parameter LUT_BITS   = 12,
    parameter LUT_FILE   = "qlut.hex"
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   en,
    input  wire [PHASE_BITS-1:0]  ftw,      // frequency tuning word
    output reg  [7:0]             dac       // 8-bit code to the R-2R ladder
);
    reg [PHASE_BITS-1:0] phase;
    reg [7:0] qlut [0:1024];
    initial $readmemh(LUT_FILE, qlut);

    wire [LUT_BITS-1:0] addr = phase[PHASE_BITS-1 -: LUT_BITS];
    wire                neg  = addr[LUT_BITS-1];              // addr >= 2048
    wire                mir  = addr[LUT_BITS-2];              // mirror within half

    // index into the quarter table, 0..1024
    wire [10:0] j = mir ? (11'd1024 - {1'b0, addr[LUT_BITS-3:0]})
                        : {1'b0, addr[LUT_BITS-3:0]};
    wire [7:0]  q = qlut[j];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase <= {PHASE_BITS{1'b0}};
            dac   <= 8'd128;
        end else if (en) begin
            // emit for the CURRENT phase, then advance -- matches SIM-0, which
            // accumulates after producing each sample.
            dac   <= neg ? (8'd128 - q - ((j == 11'd0) ? 8'd0 : 8'd1))
                         : (8'd128 + q);
            phase <= phase + ftw;
        end
    end
endmodule
