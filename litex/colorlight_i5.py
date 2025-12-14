#!/usr/bin/env python3

#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2021 Kazumoto Kojima <kkojima@rr.iij4u.or.jp>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.build.io import DDROutput

from litex_boards.platforms import colorlight_i5

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores.video import VideoHDMIPHY
from litex.soc.cores.led import LedChaser

from litex.soc.cores.gpio import GPIOOut
from litex.build.generic_platform import Subsignal, Pins, IOStandard


from litex.soc.interconnect.csr import *

from litedram.modules import M12L64322A # Compatible with EM638325-6H.
from litedram.phy import GENSDRPHY, HalfRateGENSDRPHY

from liteeth.phy.ecp5rgmii import LiteEthPHYRGMII

# CRG ----------------------------------------------------------------------------------------------

class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, use_internal_osc=False, with_usb_pll=False, with_video_pll=False, sdram_rate="1:1"):
        self.rst    = Signal()
        self.cd_sys = ClockDomain()
        if sdram_rate == "1:2":
            self.cd_sys2x    = ClockDomain()
            self.cd_sys2x_ps = ClockDomain()
        else:
            self.cd_sys_ps = ClockDomain()

        # # #

        # Clk / Rst
        if not use_internal_osc:
            clk = platform.request("clk25")
            clk_freq = 25e6
        else:
            clk = Signal()
            div = 5
            self.specials += Instance("OSCG",
                p_DIV = div,
                o_OSC = clk
            )
            clk_freq = 310e6/div

        rst_n = platform.request("cpu_reset_n")

        # PLL
        self.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~rst_n | self.rst)
        pll.register_clkin(clk, clk_freq)
        pll.create_clkout(self.cd_sys,    sys_clk_freq)
        if sdram_rate == "1:2":
            pll.create_clkout(self.cd_sys2x,    2*sys_clk_freq)
            pll.create_clkout(self.cd_sys2x_ps, 2*sys_clk_freq, phase=180) # Idealy 90° but needs to be increased.
        else:
           pll.create_clkout(self.cd_sys_ps, sys_clk_freq, phase=180) # Idealy 90° but needs to be increased.

        # USB PLL
        if with_usb_pll:
            self.usb_pll = usb_pll = ECP5PLL()
            self.comb += usb_pll.reset.eq(~rst_n | self.rst)
            usb_pll.register_clkin(clk, clk_freq)
            self.cd_usb_12 = ClockDomain()
            self.cd_usb_48 = ClockDomain()
            usb_pll.create_clkout(self.cd_usb_12, 12e6, margin=0)
            usb_pll.create_clkout(self.cd_usb_48, 48e6, margin=0)

        # Video PLL
        if with_video_pll:
            self.video_pll = video_pll = ECP5PLL()
            self.comb += video_pll.reset.eq(~rst_n | self.rst)
            video_pll.register_clkin(clk, clk_freq)
            self.cd_hdmi   = ClockDomain()
            self.cd_hdmi5x = ClockDomain()
            video_pll.create_clkout(self.cd_hdmi,    40e6, margin=0)
            video_pll.create_clkout(self.cd_hdmi5x, 200e6, margin=0)

        # SDRAM clock
        sdram_clk = ClockSignal("sys2x_ps" if sdram_rate == "1:2" else "sys_ps")
        self.specials += DDROutput(1, 0, platform.request("sdram_clock"), sdram_clk)


# Bitcoin Miner wrapper ---------------------------------------------------------------------------

class BitcoinMinerCSR(LiteXModule, AutoCSR):
    def __init__(self, platform):
        # Inputs from CPU
        self.start = CSRStorage(description="Start mining (write 1 for a pulse)")

        # Em vez de listas, declarar cada CSR individualmente para garantir
        # que o gerador de CSRs crie entradas em csr.h.
        self.block0_0  = CSRStorage(32, description="Block0 word 0")
        self.block0_1  = CSRStorage(32, description="Block0 word 1")
        self.block0_2  = CSRStorage(32, description="Block0 word 2")
        self.block0_3  = CSRStorage(32, description="Block0 word 3")
        self.block0_4  = CSRStorage(32, description="Block0 word 4")
        self.block0_5  = CSRStorage(32, description="Block0 word 5")
        self.block0_6  = CSRStorage(32, description="Block0 word 6")
        self.block0_7  = CSRStorage(32, description="Block0 word 7")
        self.block0_8  = CSRStorage(32, description="Block0 word 8")
        self.block0_9  = CSRStorage(32, description="Block0 word 9")
        self.block0_10 = CSRStorage(32, description="Block0 word 10")
        self.block0_11 = CSRStorage(32, description="Block0 word 11")
        self.block0_12 = CSRStorage(32, description="Block0 word 12")
        self.block0_13 = CSRStorage(32, description="Block0 word 13")
        self.block0_14 = CSRStorage(32, description="Block0 word 14")
        self.block0_15 = CSRStorage(32, description="Block0 word 15")

        self.block1_0  = CSRStorage(32, description="Block1 word 0")
        self.block1_1  = CSRStorage(32, description="Block1 word 1")
        self.block1_2  = CSRStorage(32, description="Block1 word 2")
        self.block1_3  = CSRStorage(32, description="Block1 word 3")
        self.block1_4  = CSRStorage(32, description="Block1 word 4")
        self.block1_5  = CSRStorage(32, description="Block1 word 5")
        self.block1_6  = CSRStorage(32, description="Block1 word 6")
        self.block1_7  = CSRStorage(32, description="Block1 word 7")
        self.block1_8  = CSRStorage(32, description="Block1 word 8")
        self.block1_9  = CSRStorage(32, description="Block1 word 9")
        self.block1_10 = CSRStorage(32, description="Block1 word 10")
        self.block1_11 = CSRStorage(32, description="Block1 word 11")
        self.block1_12 = CSRStorage(32, description="Block1 word 12")
        self.block1_13 = CSRStorage(32, description="Block1 word 13")
        self.block1_14 = CSRStorage(32, description="Block1 word 14")
        self.block1_15 = CSRStorage(32, description="Block1 word 15")

        self.target_0  = CSRStorage(32, description="Target word 0")
        self.target_1  = CSRStorage(32, description="Target word 1")
        self.target_2  = CSRStorage(32, description="Target word 2")
        self.target_3  = CSRStorage(32, description="Target word 3")
        self.target_4  = CSRStorage(32, description="Target word 4")
        self.target_5  = CSRStorage(32, description="Target word 5")
        self.target_6  = CSRStorage(32, description="Target word 6")
        self.target_7  = CSRStorage(32, description="Target word 7")

        # Outputs to CPU
        self.status      = CSRStatus(2,  description="bit0=busy, bit1=found")
        self.found_nonce = CSRStatus(32, description="Nonce encontrado")
        self.found_hash_0 = CSRStatus(32, description="Found hash word 0")
        self.found_hash_1 = CSRStatus(32, description="Found hash word 1")
        self.found_hash_2 = CSRStatus(32, description="Found hash word 2")
        self.found_hash_3 = CSRStatus(32, description="Found hash word 3")
        self.found_hash_4 = CSRStatus(32, description="Found hash word 4")
        self.found_hash_5 = CSRStatus(32, description="Found hash word 5")
        self.found_hash_6 = CSRStatus(32, description="Found hash word 6")
        self.found_hash_7 = CSRStatus(32, description="Found hash word 7")

        # Internal signals
        miner_start = Signal()
        miner_busy  = Signal()
        miner_found = Signal()
        miner_nonce = Signal(32)
        miner_hash  = Signal(256)

        block0_sig  = Signal(512)
        block1_sig  = Signal(512)
        target_sig  = Signal(256)

        # Mapear manualmente os 16 words de block0/block1/8 words de target.
        self.comb += [
            # Gera um pulso de start a partir de uma escrita em self.start
            miner_start.eq(self.start.re),

            block0_sig.eq(Cat(
                self.block0_0.storage,  self.block0_1.storage,
                self.block0_2.storage,  self.block0_3.storage,
                self.block0_4.storage,  self.block0_5.storage,
                self.block0_6.storage,  self.block0_7.storage,
                self.block0_8.storage,  self.block0_9.storage,
                self.block0_10.storage, self.block0_11.storage,
                self.block0_12.storage, self.block0_13.storage,
                self.block0_14.storage, self.block0_15.storage
            )),

            block1_sig.eq(Cat(
                self.block1_0.storage,  self.block1_1.storage,
                self.block1_2.storage,  self.block1_3.storage,
                self.block1_4.storage,  self.block1_5.storage,
                self.block1_6.storage,  self.block1_7.storage,
                self.block1_8.storage,  self.block1_9.storage,
                self.block1_10.storage, self.block1_11.storage,
                self.block1_12.storage, self.block1_13.storage,
                self.block1_14.storage, self.block1_15.storage
            )),

            # Agora o target vem dos CSRs target_0..7 (configurável pelo firmware)
            target_sig.eq(Cat(
                self.target_0.storage,  self.target_1.storage,
                self.target_2.storage,  self.target_3.storage,
                self.target_4.storage,  self.target_5.storage,
                self.target_6.storage,  self.target_7.storage
            )),

            self.status.status[0].eq(miner_busy),
            self.status.status[1].eq(miner_found),
            self.found_nonce.status.eq(miner_nonce),

            Cat(
                self.found_hash_0.status,
                self.found_hash_1.status,
                self.found_hash_2.status,
                self.found_hash_3.status,
                self.found_hash_4.status,
                self.found_hash_5.status,
                self.found_hash_6.status,
                self.found_hash_7.status
            ).eq(miner_hash)
        ]

        self.specials += Instance("bitcoin_miner",
            i_clk         = ClockSignal("sys"),
            i_rst         = ResetSignal("sys"),
            i_start       = miner_start,
            i_block0      = block0_sig,
            i_block1_tmpl = block1_sig,
            i_target      = target_sig,
            o_busy        = miner_busy,
            o_found       = miner_found,
            o_found_nonce = miner_nonce,
            o_found_hash  = miner_hash,
        )

        platform.add_source("./rtl/sha256_core.sv")
        platform.add_source("./rtl/sha256_double.sv")
        platform.add_source("./rtl/bitcoin_miner.sv")

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, board="i5", revision="7.0", toolchain="trellis", sys_clk_freq=60e6,
        with_ethernet          = False,
        with_etherbone         = False,
        local_ip               = "",
        remote_ip              = "",
        eth_phy                = 0,
        with_led_chaser        = True,
        use_internal_osc       = False,
        sdram_rate             = "1:1",
        with_video_terminal    = False,
        with_video_framebuffer = False,
        **kwargs):
        board = board.lower()
        assert board in ["i5", "i9"]
        platform = colorlight_i5.Platform(board=board, revision=revision, toolchain=toolchain)

        # CRG --------------------------------------------------------------------------------------
        with_usb_pll   = kwargs.get("uart_name", None) == "usb_acm"
        with_video_pll = with_video_terminal or with_video_framebuffer
        self.crg = _CRG(platform, sys_clk_freq,
            use_internal_osc = use_internal_osc,
            with_usb_pll     = with_usb_pll,
            with_video_pll   = with_video_pll,
            sdram_rate       = sdram_rate
        )

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, int(sys_clk_freq), ident = "LiteX SoC on Colorlight " + board.upper(), **kwargs)

        # Leds -------------------------------------------------------------------------------------
        leds_pads = [
            ("leds_ext", 0, 
                Pins("P17 P18 N18 L20 L18 G20 M18 N17"),
                IOStandard("LVCMOS33")
            )
        ]

        platform.add_extension(leds_pads)

        self.submodules.leds = GPIOOut(platform.request("leds_ext"))
        self.add_csr("leds")

        # Bitcoin miner engine (exposto via CSRs) -------------------------------------------------
        self.submodules.btcminer = BitcoinMinerCSR(platform)
        self.add_csr("btcminer")

        # SPI Flash --------------------------------------------------------------------------------
        if board == "i5":
            from litespi.modules import GD25Q16 as SpiFlashModule
        if board == "i9":
            from litespi.modules import W25Q64 as SpiFlashModule

        from litespi.opcodes import SpiNorFlashOpCodes as Codes
        self.add_spi_flash(mode="1x", module=SpiFlashModule(Codes.READ_1_1_1))

        # SDR SDRAM --------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            sdrphy_cls = HalfRateGENSDRPHY if sdram_rate == "1:2" else GENSDRPHY
            self.sdrphy = sdrphy_cls(platform.request("sdram"))
            self.add_sdram("sdram",
                phy           = self.sdrphy,
                module        = M12L64322A(sys_clk_freq, sdram_rate),
                l2_cache_size = kwargs.get("l2_size", 8192)
            )

        # Ethernet / Etherbone ---------------------------------------------------------------------
        if with_ethernet or with_etherbone:
            self.ethphy = LiteEthPHYRGMII(
                clock_pads = self.platform.request("eth_clocks", eth_phy),
                pads       = self.platform.request("eth", eth_phy),
                tx_delay = 0)
            if with_ethernet:
                self.add_ethernet(phy=self.ethphy)
            if with_etherbone:
                self.add_etherbone(phy=self.ethphy)

        if local_ip:
            local_ip = local_ip.split(".")
            self.add_constant("LOCALIP1", int(local_ip[0]))
            self.add_constant("LOCALIP2", int(local_ip[1]))
            self.add_constant("LOCALIP3", int(local_ip[2]))
            self.add_constant("LOCALIP4", int(local_ip[3]))

        if remote_ip:
            remote_ip = remote_ip.split(".")
            self.add_constant("REMOTEIP1", int(remote_ip[0]))
            self.add_constant("REMOTEIP2", int(remote_ip[1]))
            self.add_constant("REMOTEIP3", int(remote_ip[2]))
            self.add_constant("REMOTEIP4", int(remote_ip[3]))

        # Video ------------------------------------------------------------------------------------
        if with_video_terminal or with_video_framebuffer:
            self.videophy = VideoHDMIPHY(platform.request("gpdi"), clock_domain="hdmi")
            if with_video_terminal:
                self.add_video_terminal(phy=self.videophy, timings="800x600@60Hz", clock_domain="hdmi")
            if with_video_framebuffer:
                self.add_video_framebuffer(phy=self.videophy, timings="800x600@60Hz", clock_domain="hdmi")

# Build --------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=colorlight_i5.Platform, description="LiteX SoC on Colorlight I5.")
    parser.add_target_argument("--board",            default="i5",             help="Board type (i5).")
    parser.add_target_argument("--revision",         default="7.0",            help="Board revision (7.0).")
    parser.add_target_argument("--sys-clk-freq",     default=60e6, type=float, help="System clock frequency.")
    ethopts = parser.target_group.add_mutually_exclusive_group()
    ethopts.add_argument("--with-ethernet",   action="store_true",      help="Enable Ethernet support.")
    ethopts.add_argument("--with-etherbone",  action="store_true",      help="Enable Etherbone support.")
    parser.add_target_argument("--remote-ip", default="192.168.1.100",  help="Remote IP address of TFTP server.")
    parser.add_target_argument("--local-ip",  default="192.168.1.50",   help="Local IP address.")
    sdopts = parser.target_group.add_mutually_exclusive_group()
    sdopts.add_argument("--with-spi-sdcard",  action="store_true", help="Enable SPI-mode SDCard support.")
    sdopts.add_argument("--with-sdcard",      action="store_true", help="Enable SDCard support.")
    parser.add_target_argument("--eth-phy",          default=0, type=int, help="Ethernet PHY (0 or 1).")
    parser.add_target_argument("--use-internal-osc", action="store_true", help="Use internal oscillator.")
    parser.add_target_argument("--sdram-rate",       default="1:1",       help="SDRAM Rate (1:1 Full Rate or 1:2 Half Rate).")
    viopts = parser.target_group.add_mutually_exclusive_group()
    viopts.add_argument("--with-video-terminal",    action="store_true", help="Enable Video Terminal (HDMI).")
    viopts.add_argument("--with-video-framebuffer", action="store_true", help="Enable Video Framebuffer (HDMI).")
    args = parser.parse_args()

    soc = BaseSoC(board=args.board, revision=args.revision,
        toolchain              = args.toolchain,
        sys_clk_freq           = args.sys_clk_freq,
        with_ethernet          = args.with_ethernet,
        with_etherbone         = args.with_etherbone,
        local_ip               = args.local_ip,
        remote_ip              = args.remote_ip,
        eth_phy                = args.eth_phy,
        use_internal_osc       = args.use_internal_osc,
        sdram_rate             = args.sdram_rate,
        with_video_terminal    = args.with_video_terminal,
        with_video_framebuffer = args.with_video_framebuffer,
        **parser.soc_argdict
    )
    soc.platform.add_extension(colorlight_i5._sdcard_pmod_io)
    if args.with_spi_sdcard:
        soc.add_spi_sdcard()
    if args.with_sdcard:
        soc.add_sdcard()

    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))

if __name__ == "__main__":
    main()