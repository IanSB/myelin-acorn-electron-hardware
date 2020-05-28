#!/usr/bin/python

# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ------------
# post_box_usb
# ------------

# by Phillip Pearson

# A USB interface for the POST connectors found on most Archimedes and Risc PC
# class machines.

# - ATSAMD21 32-pin TQFP
# - SWD header and pullups
# - Power LED
# - Micro USB socket, 3v3 regulator + capacitors
# - LCMXO256 FPGA
# - 74LCX125 hot swap buffer
# - 74HCT125 5V buffer

# The back to back buffers are used to prevent odd things from happening when
# the two sides of the system are powered up or down at different times.  The
# 74HCT125 is powered by the target machine, and everything else is powered
# from USB.  This makes it possible to reset everything by unplugging the USB
# cable, and prevents the target machine from taking power from the output
# buffer.

# (done) Verify 74HCT125 and 74LCX125 pinout and wiring
# (done) Verify that 1k series resistor and 10k pullup are sensible.
# TODO move the pull resistors to testack_noe_buf and target_reset_noe_buf so we don't get a resistor divider at all
# TODO connect all /OE pins on the 74LCX125 to an FPGA output and add a 10k pull resistor to 3V3
# TODO add a couple of LEDs driven by microcontroller GPIOs
# TODO add lots of staples

import sys, os
here = os.path.dirname(sys.argv[0])
sys.path.insert(0, os.path.join(here, "../../third_party/myelin-kicad.pretty"))
import myelin_kicad_pcb
Pin = myelin_kicad_pcb.Pin

PROJECT_NAME = 'post_box_usb'


mcu = myelin_kicad_pcb.Component(
    footprint="Housings_QFP:TQFP-32_7x7mm_Pitch0.8mm",
    identifier="MCU",
    value="ATSAMD21E18A-AU",  # 256k flash, 32k sram, 32 pins
    desc="IC ARM MCU; https://www.digikey.com/products/en?keywords=ATSAMD21E18A-AU-ND",
    pins=[
        # We use a 32.768kHz crystal and the 96MHz FDPLL with some massive
        # multiplier.  This seems a bit weird, but all the ATSAMD21 designs I
        # can find are clocked this way.  The FDPLL has an input divider, so it
        # should be possible to use an 8MHz input, but nobody seems to do that.
        Pin(1, "PA00/XIN32", ["XTAL_IN"]),
        Pin(2, "PA01/XOUT32", ["XTAL_OUT"]),
        Pin(3, "PA02/AIN0", ["last_transaction_was_input"]),
        Pin(4, "PA03/ADC_VREFA/AIN1", ["PA03"]),
        Pin(5, "PA04/SERCOM0.0/AIN4", ["fpga_TDO"]),
        Pin(6, "PA05/SERCOM0.1/AIN5", ["fpga_TCK"]),
        Pin(7, "PA06/SERCOM0.2/AIN6", ["fpga_TMS"]),
        Pin(8, "PA07/SERCOM0.3/AIN7", ["fpga_TDI"]),
        Pin(9, "VDDANA", ["3V3"]),  # decouple to GND
        Pin(10, "GND", ["GND"]),
        Pin(11, "PA08/NMI/SERCOM2.0/AIN16", ["fpga_spi_mosi"]),
        Pin(12, "PA09/SERCOM2.1/AIN17", ["fpga_spi_sck"]),
        Pin(13, "PA10/SERCOM2.2/AIN18", ["fpga_clock_48mhz"]),  # GCLK_IO[4] - clock output for FPGA
        Pin(14, "PA11/SERCOM2.3/AIN19", ["rx_ready"]),  # also GCLK_IO[5] if we want a second clock output
        Pin(15, "PA14/XIN/SERCOM4.2", ["fpga_spi_cs"]),
        Pin(16, "PA15/XOUT/SERCOM4.3", ["fpga_spi_miso"]),
        Pin(17, "PA16/SERCOM1.0", ["tx_pending"]),
        Pin(18, "PA17/SERCOM1.1", ["target_power_out"]),
        Pin(19, "PA18/SERCOM1.2", ["PA18"]),
        Pin(20, "PA19/SERCOM1.3", ["PA19"]),
        Pin(21, "PA22/SERCOM3.0", ["mcu_TXD"]),
        Pin(22, "PA23/SERCOM3.1/USBSOF", ["mcu_RXD"]),
        Pin(23, "PA24/USBDM", ["USBDM"]),
        Pin(24, "PA25/USBDP", ["USBDP"]),
        Pin(25, "PA27", ["PA27"]),
        Pin(26, "nRESET", ["mcu_RESET"]),
        Pin(27, "PA28", ["reset_in"]),
        Pin(28, "GND", ["GND"]),
        Pin(29, "VDDCORE", ["VDDCORE"]),  # regulated output, needs cap to GND
        Pin(30, "VDDIN", ["3V3"]),  # decouple to GND
        Pin(31, "PA30/SWCLK", ["mcu_SWCLK"]),
        Pin(32, "PA31/SWDIO", ["mcu_SWDIO"]),
    ],
)
mcu_cap1 = myelin_kicad_pcb.C0805("100n", "GND", "3V3", ref="C3")
mcu_cap2 = myelin_kicad_pcb.C0805("100n", "GND", "3V3", ref="C4")
mcu_cap3 = myelin_kicad_pcb.C0805("1u", "GND", "VDDCORE", ref="C5")
# SAM D21 has an internal pull-up, so this is optional
mcu_reset_pullup = myelin_kicad_pcb.R0805("10k", "mcu_RESET", "3V3", ref="R1")
# The SAM D21 datasheet says a 1k pullup on SWCLK is critical for reliability
mcu_swclk_pullup = myelin_kicad_pcb.R0805("1k", "mcu_SWCLK", "3V3", ref="R2")

# SWD header for programming and debug using a Tag-Connect TC2030-CTX
swd = myelin_kicad_pcb.Component(
    footprint="Tag-Connect_TC2030-IDC-FP_2x03_P1.27mm_Vertical",
    identifier="SWD",
    value="swd",
    exclude_from_bom=True,
    pins=[
        # Tag-Connect SWD layout: http://www.tag-connect.com/Materials/TC2030-CTX.pdf
        Pin(1, "VCC",       "3V3"),
        Pin(2, "SWDIO/TMS", "mcu_SWDIO"),
        Pin(3, "nRESET",    "mcu_RESET"),
        Pin(4, "SWCLK/TCK", "mcu_SWCLK"),
        Pin(5, "GND",       "GND"),
        Pin(6, "SWO/TDO"),  # NC because Cortex-M0 doesn't use these
    ],
)


# SWD header for programming and debug
swd2 = myelin_kicad_pcb.Component(
    footprint="Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD",
    identifier="SWD2",
    value="swd",
    pins=[
        # Pin numbers zig-zag:
        # 1 VCC  2 SWDIO
        # 3 GND  4 SWCLK
        # 5 GND  6 NC
        # 7 NC   8 NC
        # 9 NC  10 /RESET
        Pin(1, "VTref", "3V3"),
        Pin(2, "SWDIO", "mcu_SWDIO"),
        Pin(3, "GND",   "GND"),
        Pin(4, "SWCLK", "mcu_SWCLK"),
        Pin(5, "GND",   "GND"),
        Pin(6, "NC"),
        Pin(7, "NC"),
        Pin(8, "NC"),
        Pin(9, "GND",   "GND"),
        Pin(10, "RESET", "mcu_RESET"),
    ],
)


power_led_r = myelin_kicad_pcb.R0805("330R", "3V3", "power_led_anode", ref="R3")
power_led = myelin_kicad_pcb.DSOD323("led", "GND", "power_led_anode", ref="L1")

# Micro USB socket, mounted on the bottom of the board
micro_usb = myelin_kicad_pcb.Component(
    footprint="myelin-kicad:micro_usb_b_smd_molex",
    identifier="USB",
    value="usb",
    desc="Molex 1050170001 (Digikey WM1399CT-ND) surface mount micro USB socket with mounting holes.",
    pins=[
        Pin(1, "V", ["5V"]),  # input from host
        Pin(2, "-", ["USBDM"]),
        Pin(3, "+", ["USBDP"]),
        Pin(4, "ID", ["USB_ID"]),
        Pin(5, "G", ["GND"]),
    ],
)

# USB-A (host) socket
usb_host = myelin_kicad_pcb.Component(
    footprint="Connectors:USB_A",
    identifier="HOST",
    value="usb host",
    pins=[
        Pin(1, "V", ["5V"]),  # output to device
        Pin(2, "-", ["USBDM"]),
        Pin(3, "+", ["USBDP"]),
        Pin(4, "G", ["GND"]),
    ],
)

# MC-146 32.768000 kHz crystal
# load capacitance 12.5pF
# CL = (C1 * C2) / (C1 + C2) + Cstray
#    = C1*C1 / 2*C1 + Cstray
# 12.5pF = C1/2 + 5pF
# C1 = 2(12.5pF - 5pF)
#    = 15pF
# So we should use two 15pF caps
xtal = myelin_kicad_pcb.Component(
    footprint="Crystals:Crystal_SMD_SeikoEpson_MC146-4pin_6.7x1.5mm_HandSoldering",
    identifier="X1",
    value="MC146 32768Hz",
    pins=[
        Pin(1, "X1", ["XTAL_IN"]),
        Pin(4, "X2", ["XTAL_OUT"]),
    ],
)
xtal_cap1 = myelin_kicad_pcb.C0805("15p", "GND", "XTAL_IN", ref="C6")
xtal_cap1 = myelin_kicad_pcb.C0805("15p", "GND", "XTAL_OUT", ref="C7")

regulator = myelin_kicad_pcb.Component(
    footprint="TO_SOT_Packages_SMD:SOT-89-3",
    identifier="U1",
    value="MCP1700T-3302E/MB",
    pins=[
        Pin(2, "VIN", ["5V"]),
        Pin(3, "VOUT", ["3V3"]),
        Pin(1, "GND", ["GND"]),
    ],
)
reg_in_cap = myelin_kicad_pcb.C0805("1u", "GND", "5V", ref="C1")
reg_out_cap = myelin_kicad_pcb.C0805("1u", "3V3", "GND", ref="C2")

# 24 pins total:
# - 20 x gpio
# - 3v3, 5v, GND
# - /reset
# skipping: 2nd 3v3/gnd, usbdb/usbdp, swdio/swclk, xtalin/xtalout

pin_header = myelin_kicad_pcb.Component(
    footprint="Connector_PinHeader_2.54mm:PinHeader_2x13_P2.54mm_Vertical",
    identifier="CON",
    value="pins",
    pins=[
        Pin(1, "", ["3V3"]),
        Pin(2, "", ["GND"]),
        Pin(3, "", ["fpga_TDO"]),
        Pin(4, "", ["PA03"]),
        Pin(5, "", ["fpga_TMS"]),
        Pin(6, "", ["fpga_TCK"]),
        Pin(7, "", ["last_transaction_was_input"]),
        Pin(8, "", ["fpga_TDI"]),
        Pin(9, "", ["fpga_spi_sck"]),
        Pin(10, "", ["fpga_spi_mosi"]),
        Pin(11, "", ["rx_ready"]),
        Pin(12, "", ["fpga_clock_48mhz"]),
        Pin(13, "", ["fpga_spi_miso"]),
        Pin(14, "", ["fpga_spi_cs"]),
        Pin(15, "", ["PA27"]),
        Pin(16, "", ["reset_in"]),
        Pin(17, "", ["target_power_out"]),
        Pin(18, "", ["tx_pending"]),
        Pin(19, "", ["PA19"]),
        Pin(20, "", ["PA18"]),
        Pin(21, "", ["mcu_RXD"]),
        Pin(22, "", ["mcu_TXD"]),
        Pin(23, "", ["GND"]),
        Pin(24, "", ["3V3"]),
        Pin(25, "", ["GND"]),
        Pin(26, "", ["5V"]),
    ],
)

power_header = myelin_kicad_pcb.Component(
    footprint="Pin_Headers:Pin_Header_Straight_1x02_Pitch2.54mm",
    identifier="PWR",
    value="reset",
    pins=[
        Pin(1, "", ["3V3"]),
        Pin(2, "", ["5V"]),
    ],
)

reset_header = myelin_kicad_pcb.Component(
    footprint="Pin_Headers:Pin_Header_Straight_1x02_Pitch2.54mm",
    identifier="RST",
    value="reset",
    pins=[
        Pin(1, "", ["GND"]),
        Pin(2, "", ["mcu_RESET"]),
    ],
)

# TODO commit lattice_tn100 part to myelin-kicad.pretty repo
# Lattice lcmxo256 MachXO FPGA, in 100-pin TQFP package
fpga = myelin_kicad_pcb.Component(
    footprint="myelin-kicad:lattice_tn100",  # 14x14mm 100-pin TQFP
    identifier="FPGA",
    value="LCMXO256",
    pins=[
        Pin(  1, "PL2A",         "fpga_GPIO47"),
        Pin(  2, "PL2B",         "fpga_GPIO44"),
        Pin(  3, "PL3A",         "fpga_GPIO45"),
        Pin(  4, "PL3B",         "fpga_GPIO42"),
        Pin(  5, "PL3C",         "fpga_GPIO43"),
        Pin(  6, "PL3D",         "fpga_GPIO40"),
        Pin(  7, "PL4A",         "fpga_GPIO41"),
        Pin(  8, "PL4B",         "fpga_GPIO38"),
        Pin(  9, "PL5A",         "fpga_GPIO39"),
        Pin( 10, "VCCIO1",       ["3V3"]),
        Pin( 11, "PL5B",         "fpga_GPIO36"),
        Pin( 12, "GNDIO1",       ["GND"]),
        Pin( 13, "PL5C",         ""),
        Pin( 14, "PL5D_GSRN",    "fpga_GPIO37"),
        Pin( 15, "PL6A",         "fpga_GPIO34"),
        Pin( 16, "PL6B_TSALL",   "fpga_GPIO35"),
        Pin( 17, "PL7A",         ""),
        Pin( 18, "PL7B",         ""),
        Pin( 19, "PL7C",         ""),
        Pin( 20, "PL7D",         ""),
        Pin( 21, "PL8A",         ""),
        Pin( 22, "PL8B",         ""),
        Pin( 23, "PL9A",         ""),
        Pin( 24, "VCCIO1",       ["3V3"]),
        Pin( 25, "GNDIO1",       ["GND"]),
        Pin( 26, "TMS",          ["fpga_TMS"]),  # has an internal pull-up resistor
        Pin( 27, "PL9B",         "target_power_3v"),
        Pin( 28, "TCK",          ["fpga_TCK"]),  # needs external 4k7 pull-DOWN resistor
        Pin( 29, "PB2A",         "target_reset_noe"),
        Pin( 30, "PB2B",         "testack_noe"),
        Pin( 31, "TDO",          ["fpga_TDO"]),  # has an internal pull-up resistor
        Pin( 32, "PB2C",         "testreq_3v"),
        Pin( 33, "TDI",          ["fpga_TDI"]),  # has an internal pull-up resistor
        Pin( 34, "PB2D",         "fpga_GPIO0"),
        Pin( 35, "VCC",          ["3V3"]),
        Pin( 36, "PB3A_PCLK1_1", "fpga_GPIO1"),
        Pin( 37, "PB3B",         "fpga_GPIO2"),
        Pin( 38, "PB3C_PCLK1_0", "fpga_OSC_in"),
        Pin( 39, "PB3D",         "fpga_GPIO3"),
        Pin( 40, "GND",          ["GND"]),
        Pin( 41, "VCCIO1",       ["3V3"]),
        Pin( 42, "GNDIO1",       ["GND"]),
        Pin( 43, "PB4A",         "fpga_GPIO4"),
        Pin( 44, "PB4B",         "fpga_GPIO5"),
        Pin( 45, "PB4C",         "fpga_GPIO6"),
        Pin( 46, "PB4D",         "fpga_GPIO7"),
        Pin( 47, "PB5A",         "fpga_GPIO8"),
        Pin( 48, "SLEEPN",       ["SLEEPN"]),  # needs external 4k7 pull-up resistor
        Pin( 49, "PB5C",         "fpga_GPIO9"),
        Pin( 50, "PB5D",         "fpga_GPIO10"),
        Pin( 51, "PR9B",         "fpga_GPIO11"),
        Pin( 52, "PR9A",         "fpga_GPIO12"),
        Pin( 53, "PR8B",         "fpga_GPIO13"),
        Pin( 54, "PR8A",         "fpga_GPIO14"),
        Pin( 55, "PR7D",         "fpga_GPIO15"),
        Pin( 56, "PR7C",         "fpga_GPIO16"),
        Pin( 57, "PR7B",         "fpga_GPIO17"),
        Pin( 58, "PR7A",         "fpga_GPIO18"),
        Pin( 59, "PR6B",         "fpga_GPIO19"),
        Pin( 60, "VCCIO0",       ["3V3"]),
        Pin( 61, "PR6A",         "fpga_GPIO20"),
        Pin( 62, "GNDIO0",       ["GND"]),
        Pin( 63, "PR5D",         "fpga_GPIO21"),
        Pin( 64, "PR5C",         "fpga_GPIO22"),
        Pin( 65, "PR5B",         "fpga_GPIO23"),
        Pin( 66, "PR5A",         "fpga_GPIO24"),
        Pin( 67, "PR4B",         "fpga_GPIO25"),
        Pin( 68, "PR4A",         "fpga_GPIO26"),
        Pin( 69, "PR3D",         "fpga_GPIO27"),
        Pin( 70, "PR3C",         "fpga_GPIO28"),
        Pin( 71, "PR3B",         "fpga_GPIO29"),
        Pin( 72, "PR3A",         "fpga_GPIO30"),
        Pin( 73, "PR2B",         "fpga_GPIO31"),
        Pin( 74, "VCCIO0",       ["3V3"]),
        Pin( 75, "GNDIO0",       ["GND"]),
        Pin( 76, "PR2A",         "fpga_GPIO32"),
        Pin( 77, "PT5C",         "fpga_GPIO33"),
        Pin( 78, "PT5B",         "mcu_RXD"),
        Pin( 79, "PT5A",         "mcu_TXD"),
        Pin( 80, "PT4F",         "PA19"),
        Pin( 81, "PT4E",         "PA18"),
        Pin( 82, "PT4D",         "target_power_out"),
        Pin( 83, "PT4C",         "tx_pending"),
        Pin( 84, "GND",          ["GND"]),
        Pin( 85, "PT4B_PCLK0_1", ["rx_ready"]),
        Pin( 86, "PT4A_PCLK0_0", ["fpga_clock_48mhz"]),
        Pin( 87, "PT3D",         "PA27"),
        Pin( 88, "VCCAUX",       ["3V3"]),
        Pin( 89, "PT3C",         "reset_in"),
        Pin( 90, "VCC",          ["3V3"]),
        Pin( 91, "PT3B",         "fpga_spi_miso"),
        Pin( 92, "VCCIO0",       ["3V3"]),
        Pin( 93, "GNDIO0",       ["GND"]),
        Pin( 94, "PT3A",         "fpga_spi_cs"),
        Pin( 95, "PT2F",         "fpga_spi_sck"),
        Pin( 96, "PT2E",         "fpga_spi_mosi"),
        Pin( 97, "PT2D",         "last_transaction_was_input"),
        Pin( 98, "PT2C",         "PA03"),
        Pin( 99, "PT2B",         ""),
        Pin(100, "PT2A",         "fpga_GPIO46"),
    ],
)
machxo_sleepn_pullup = myelin_kicad_pcb.R0805("4k7", "SLEEPN", "3V3", ref="R4")
machxo_tck_pulldown = myelin_kicad_pcb.R0805("4k7", "fpga_TCK", "GND", ref="R5")

lpf_fn = '%s.lpf' % PROJECT_NAME
with open(lpf_fn, 'w') as fpga_lpf:
    for pin in fpga.pins:
        nets = [net for net in pin.nets if net and net not in ('GND', '3V3', 'fpga_TMS', 'fpga_TCK', 'fpga_TDI', 'fpga_TDO', 'SLEEPN')]
        if not nets: continue
        net, = nets
        print('LOCATE COMP "%s" SITE "%d" ;' % (net, pin.number), file=fpga_lpf)
        print('IOBUF PORT "%s" IO_TYPE=LVCMOS33 PULLMODE=NONE DRIVE=NA SLEWRATE=FAST OPENDRAIN=OFF INF=OFF ;' % (net,), file=fpga_lpf)
    print("Wrote Lattice-formatted pinout suitable for copying into project .lpf as %s" % lpf_fn)

# The LCMXO256 has a ton of power/gnd pairs!
fpga_caps = [
    myelin_kicad_pcb.C0805("100n", "3V3", "GND", ref="C8"),
    myelin_kicad_pcb.C0805("100n", "3V3", "GND", ref="C9"),
    myelin_kicad_pcb.C0805("100n", "3V3", "GND", ref="C10"),
    myelin_kicad_pcb.C0805("100n", "3V3", "GND", ref="C11"),
    myelin_kicad_pcb.C0805("100n", "3V3", "GND", ref="C12"),
    myelin_kicad_pcb.C0805("100n", "3V3", "GND", ref="C13", handsoldering=False),
    myelin_kicad_pcb.C0805("100n", "3V3", "GND", ref="C14"),
    myelin_kicad_pcb.C0805("100n", "3V3", "GND", ref="C15"),
]

# MachXO/MachXO2 JTAG header, Lattice format
# See: https://github.com/google/myelin-acorn-electron-hardware/blob/master/notes/pld_programming_and_jtag.md
fpga_jtag = myelin_kicad_pcb.Component(
    footprint="Connector_Multicomp:Multicomp_MC9A12-1034_2x05_P2.54mm_Vertical",
    identifier="FPGA_JTAG",
    value="lattice jtag",
    desc="2x5 header for JTAG programming.  Use generic 0.1 inch header strip or Digikey ED1543-ND.",
    pins=[
        Pin( 1, "TCK",  "fpga_TCK"), # top left
        Pin( 2, "GND",  "GND"),      # top right
        Pin( 3, "TMS",  "fpga_TMS"),
        Pin( 4, "GND",  "GND"),
        Pin( 5, "TDI",  "fpga_TDI"),
        Pin( 6, "VCC",  "3V3"),
        Pin( 7, "TDO",  "fpga_TDO"),
        Pin( 8, "INIT", ""),  # INITN on machxo2, NC on machxo
        Pin( 9, "TRST", ""),  # DONE on machxo2, NC on machxo
        Pin(10, "PROG", ""),  # PROGRAMN on machxo2, NC on machxo
    ],
)

fpga_gpio = myelin_kicad_pcb.Component(
    footprint="Connector_PinHeader_2.54mm:PinHeader_2x20_P2.54mm_Vertical",
    identifier="FPGA_IO",
    value="pins",
    pins=[
        Pin( 1, "", ["GND"]),
        Pin( 2, "", ["3V3"]),
        Pin( 3, "", ["fpga_GPIO0"]),
        Pin( 4, "", ["fpga_GPIO1"]),
        Pin( 5, "", ["fpga_GPIO2"]),
        Pin( 6, "", ["fpga_GPIO3"]),
        Pin( 7, "", ["fpga_GPIO4"]),
        Pin( 8, "", ["fpga_GPIO5"]),
        Pin( 9, "", ["fpga_GPIO6"]),
        Pin(10, "", ["fpga_GPIO7"]),
        Pin(11, "", ["fpga_GPIO8"]),
        Pin(12, "", ["fpga_GPIO9"]),
        Pin(13, "", ["fpga_GPIO10"]),
        Pin(14, "", ["fpga_GPIO11"]),
        Pin(15, "", ["fpga_GPIO12"]),
        Pin(16, "", ["fpga_GPIO13"]),
        Pin(17, "", ["fpga_GPIO14"]),
        Pin(18, "", ["fpga_GPIO15"]),
        Pin(19, "", ["fpga_GPIO16"]),
        Pin(20, "", ["fpga_GPIO17"]),
        Pin(21, "", ["fpga_GPIO18"]),
        Pin(22, "", ["fpga_GPIO19"]),
        Pin(23, "", ["fpga_GPIO20"]),
        Pin(24, "", ["fpga_GPIO21"]),
        Pin(25, "", ["fpga_GPIO22"]),
        Pin(26, "", ["fpga_GPIO23"]),
        Pin(27, "", ["fpga_GPIO24"]),
        Pin(28, "", ["fpga_GPIO25"]),
        Pin(29, "", ["fpga_GPIO26"]),
        Pin(30, "", ["fpga_GPIO27"]),
        Pin(31, "", ["fpga_GPIO28"]),
        Pin(32, "", ["fpga_GPIO29"]),
        Pin(33, "", ["fpga_GPIO30"]),
        Pin(34, "", ["fpga_GPIO31"]),
        Pin(35, "", ["fpga_GPIO32"]),
        Pin(36, "", ["fpga_GPIO33"]),
        Pin(37, "", ["GND"]),
        Pin(38, "", ["3V3"]),
        Pin(39, "", ["GND"]),
        Pin(40, "", ["5V"]),
    ],
)

fpga_gpio_top = myelin_kicad_pcb.Component(
    footprint="Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical",
    identifier="FPGA_IO2",
    value="pins",
    pins=[
        Pin( 1, "", ["GND"]),
        Pin( 2, "", ["3V3"]),
        Pin( 3, "", ["fpga_GPIO34"]),
        Pin( 4, "", ["fpga_GPIO35"]),
        Pin( 5, "", ["fpga_GPIO36"]),
        Pin( 6, "", ["fpga_GPIO37"]),
        Pin( 7, "", ["fpga_GPIO38"]),
        Pin( 8, "", ["fpga_GPIO39"]),
        Pin( 9, "", ["fpga_GPIO40"]),
        Pin(10, "", ["fpga_GPIO41"]),
        Pin(11, "", ["fpga_GPIO42"]),
        Pin(12, "", ["fpga_GPIO43"]),
        Pin(13, "", ["fpga_GPIO44"]),
        Pin(14, "", ["fpga_GPIO45"]),
        Pin(15, "", ["fpga_GPIO46"]),
        Pin(16, "", ["fpga_GPIO47"]),
    ],
)

# 74LCX buffer, powered by the 3V side.  This is here to provide some hot swap
# tolerance; its inputs and outputs go high impedance when it's unpowered, so
# the 3V side won't end up parasitically powered if the unit is connected to a
# powered target but not a USB port.

# An alternative here could have been to not draw power from the USB port, but
# it's nice to be able to have the unit accessible even when not attached to a
# target.

# The ordering code for 74LCX125 in SO-14 is a bit of a mystery.  Every
# datasheet seems to list different codes, but the one from the onsemi.com
# page lists -M as 0.15" wide SO-14, and -MX as the same except on tape/reel.

# I've also seen -D for SOIC and -DT for TSSOP, so that might be an option too.
hotswap_buf = [
    [
        myelin_kicad_pcb.Component(
            footprint="Package_SO:SOIC-14_3.9x8.7mm_P1.27mm",
            identifier=ident,
            value="74LCX125M",
            # https://www.onsemi.com/products/standard-logic/buffers/74lcx125
            desc="IC buffer 4-bit OC hot swap; https://www.digikey.com/product-detail/en/on-semiconductor/74LCX125MX/74LCX125MXCT-ND/965496",
            pins=[
                Pin( 1, "1nOE", conn[0][0]),
                Pin( 2, "1A",   conn[0][1]),
                Pin( 3, "1Y",   conn[0][2]),
                Pin( 4, "2nOE", conn[1][0]),
                Pin( 5, "2A",   conn[1][1]),
                Pin( 6, "2Y",   conn[1][2]),
                Pin( 7, "GND",  "GND"),
                Pin( 8, "3Y",   conn[2][2]),
                Pin( 9, "3A",   conn[2][1]),
                Pin(10, "3nOE", conn[2][0]),
                Pin(11, "4Y",   conn[3][2]),
                Pin(12, "4A",   conn[3][1]),
                Pin(13, "4nOE", conn[3][0]),
                Pin(14, "VCC",  power),
            ],
        ),
        myelin_kicad_pcb.C0805("100n", "GND", power, ref="DC?"),
    ]
    for ident, power, conn in [
        (
            "HSBUF",
            "3V3",
            [
                # [nOE, input, output]
                ["GND",        "testack_noe",      "testack_noe_buf"],
                ["GND",        "testreq",          "testreq_3v"],
                ["GND",        "target_5V",        "target_power_3v"],
                ["GND",        "target_reset_noe", "target_reset_noe_buf"],
            ]
        )
    ]
]

# These resistors prevent the 5V side of things from being powered by the
# outputs from the 74LCX125.
testack_inter_buf_r = myelin_kicad_pcb.R0805("1k", "testack_noe_buf", "testack_noe_buf_r", ref="R7")
target_reset_inter_buf_r = myelin_kicad_pcb.R0805("1k", "target_reset_noe_buf", "target_reset_noe_buf_r", ref="R8")

# These resistors prevent the 74HCT125 on the 5V side from driving testack or
# reset when the 3V side is unpowered.
testack_noe_pullup = myelin_kicad_pcb.R0805("10k", "testack_noe_buf_r", "target_5V", "R9")
target_reset_pullup = myelin_kicad_pcb.R0805("10k", "target_reset_noe_buf_r", "target_5V", "R10")

# 75HCT125 buffer, powered by the 5V side
out_buf = [
    [
        myelin_kicad_pcb.Component(
            footprint="Package_SO:SOIC-14_3.9x8.7mm_P1.27mm",
            identifier=ident,
            value="74HCT125D",
            desc="IC buffer 4-bit OC; https://www.digikey.com/product-detail/en/nexperia-usa-inc/74HCT125D-653/1727-2834-1-ND/763401",
            pins=[
                Pin( 1, "1nOE", conn[0][0]),
                Pin( 2, "1A",   conn[0][1]),
                Pin( 3, "1Y",   conn[0][2]),
                Pin( 4, "2nOE", conn[1][0]),
                Pin( 5, "2A",   conn[1][1]),
                Pin( 6, "2Y",   conn[1][2]),
                Pin( 7, "GND",  "GND"),
                Pin( 8, "3Y",   conn[2][2]),
                Pin( 9, "3A",   conn[2][1]),
                Pin(10, "3nOE", conn[2][0]),
                Pin(11, "4Y",   conn[3][2]),
                Pin(12, "4A",   conn[3][1]),
                Pin(13, "4nOE", conn[3][0]),
                Pin(14, "VCC",  power),
            ],
        ),
        myelin_kicad_pcb.C0805("100n", "GND", power, ref="DC?"),
    ]
    for ident, power, conn in [
        (
            "OUTBUF",
            "target_5V",
            [
                # [nOE, input, output]
                ["testack_noe_buf_r",      "target_5V", "testack"],
                ["target_reset_noe_buf_r", "GND",       "target_reset"],
                ["target_5V",              "GND",       ""],
                ["target_5V",              "GND",       ""],
            ]
        )
    ]
]

post_header = myelin_kicad_pcb.Component(
    footprint="Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
    identifier="POST",
    value="pins",
    pins=[
        Pin(1, "", "target_5V"),
        Pin(2, "", "target_D0"),
        Pin(3, "", "testreq"),
        Pin(4, "", "testack"),
        Pin(5, "", "target_reset"),
        Pin(6, "", "GND"),
    ],
)

target_D0_pullup = myelin_kicad_pcb.R0805("2k2", "target_D0", "target_5V", ref="R6")

for n in range(20):
    single_staple = myelin_kicad_pcb.Component(
        footprint="myelin-kicad:via_single",
        identifier="staple_single%d" % (n+1),
        value="",
        pins=[Pin(1, "GND", ["GND"])],
    )


myelin_kicad_pcb.dump_netlist("%s.net" % PROJECT_NAME)
