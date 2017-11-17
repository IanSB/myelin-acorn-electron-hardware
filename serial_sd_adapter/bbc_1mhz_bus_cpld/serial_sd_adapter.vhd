-- Copyright 2017 Google Inc.
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

-- This implements a fast serial port with help from an AVR.  It also includes
-- some code from spi_sd_card.vhd to support MMFS (bit-banged SD card interface)
-- and UPURS (bit-banged serial)

entity serial_sd_adapter is
    Port (
        -- Pins that connect to the BBC 1MHz Bus

        bbc_A : in std_logic_vector(7 downto 0);
        bbc_D : inout std_logic_vector(7 downto 0);

        bbc_nPGFC : in std_logic;
        bbc_nPGFD : in std_logic;

        bbc_1MHZE : in std_logic;
        bbc_RnW : in std_logic;
        bbc_nIRQ : in std_logic;
        bbc_nNMI : in std_logic;
        bbc_nRESET : in std_logic;

        -- AVR interface: MISO, MOSI, SCK, /SS, INT.
        -- The first four are a standard SPI port, with the AVR as
        -- master and CPLD as slave.  INT is an output from the CPLD
        -- that goes high when we have a byte to send to the AVR.

        avr_INT : out std_logic;
        avr_MISC1 : in std_logic;
        avr_MISO : out std_logic;
        avr_MOSI : in std_logic;
        avr_SCK : in std_logic;
        avr_nSD_SEL : in std_logic;
        avr_nSS : in std_logic;

        -- SD interface: MISO, MOSI, SCK, /SS
        -- These are wired to the pins on the micro SD card socket.

        sd_MISO : in std_logic;
        sd_MOSI : out std_logic;
        sd_SCK : out std_logic;
        sd_nSS : out std_logic
    );
end serial_sd_adapter;

architecture Behavioural of serial_sd_adapter is

    ---- Fast SPI port (slave, for AVR) ----

    signal int_avr_MOSI : std_logic; -- input from AVR
    signal int_avr_MISO : std_logic; -- output to AVR
    signal int_avr_SCK : std_logic; -- input from AVR
    signal int_avr_nSS : std_logic; -- input from AVR
    signal int_avr_INT : std_logic; -- output to AVR
    signal int_avr_nSD_SEL : std_logic; -- input from AVR

    signal nAVR_SPI_REG_ACCESS : std_logic; -- '0' when A = &FCA0;
    signal nAVR_SPI_STATUS_REG_ACCESS : std_logic; -- '0' when A = &FCA1;

    -- we use a toggle synchronizer to know if the buffer is full or empty.
    -- RECEPTION FROM AVR TO CPLD+ELK:
    -- on the avr side, it's safe to receive a byte if avr_RXD_state = elk_RXD_state_sync
    -- on the elk side, it's safe to read a byte if elk_RXD_state != avr_RXD_state_sync
    -- we just use a single flip flop to synchronize in each case, because there's always
    -- a longish settling time.
    -- TRANSMISSION FROM ELK+CPLD TO AVR:
    -- it's safe to accept a byte from the elk for transmission if elk_TXD_state == avr_TXD_state_sync
    -- it's safe to transmit a byte to the avr if avr_TXD_state != elk_TXD_state_sync

    signal avr_RXD_state : std_logic := '0'; -- toggles whenever the CPLD receives a byte from the AVR
    signal avr_RXD_state_sync : std_logic := '0'; -- avr_RXD_state synchronized to bbc_1MHZE
    signal elk_RXD_state : std_logic := '0'; -- toggles when the elk reads a byte
    signal elk_RXD_state_sync : std_logic := '0'; -- elk_RXD_state synchronized to int_avr_SCK

    signal avr_TXD_state : std_logic := '0'; -- toggles whenever the CPLD sends a byte to the AVR
    signal avr_TXD_state_sync : std_logic := '0'; -- avr_TXD_state synchronized to bbc_1MHZE
    signal elk_TXD_state : std_logic := '0'; -- toggles when the elk writes a byte
    signal elk_TXD_state_sync : std_logic := '0'; -- elk_TXD_state synchronized to int_avr_SCK

    signal avr_RXD : std_logic_vector(7 downto 0); -- byte received from AVR
    signal avr_TXD : std_logic_vector(7 downto 0); -- next byte to transmit / being transmitted to AVR

    -- signals used during an SPI transaction
    signal avr_spi_SHIFT : std_logic_vector(7 downto 0); -- SPI shift register
    signal avr_spi_bit_count : std_logic_vector(3 downto 0); -- SPI bit counter for transfers
    signal avr_spi_receiving : std_logic := '0'; -- copy bits into avr_RXD and toggle avr_RXD_state when done
    signal avr_spi_transmitting : std_logic := '0'; -- toggle avr_TXD_state when done

    ---- SPI (master, for SD card) ---

    signal bitbang_MOSI : std_logic := '1';
    signal bitbang_SCK : std_logic := '1';
    signal bitbang_nSS : std_logic := '0';

    ---- Plus 1 workalike registers ----

    -- chip selects
    signal nDATA_REG_ACCESS : std_logic; -- '0' when A = &FC71
    signal nSTATUS_REG_ACCESS : std_logic; -- '0' when A = &FC72

begin

    -- mappings to actual pins

    int_avr_MOSI <= avr_MOSI;
    avr_MISO <= 'Z' when int_avr_nSS = '1' else
        sd_MISO when int_avr_nSD_SEL = '0' else
        int_avr_MISO;
    int_avr_SCK <= avr_SCK;
    int_avr_nSS <= avr_nSS;
    int_avr_nSD_SEL <= avr_nSD_SEL;
    avr_INT <= int_avr_INT;

    sd_nSS <= int_avr_nSS when int_avr_nSD_SEL = '0' else bitbang_nSS;
    sd_MOSI <= int_avr_MOSI when int_avr_nSD_SEL = '0' else bitbang_MOSI;
    sd_SCK <= int_avr_SCK when int_avr_nSD_SEL = '0' else bitbang_SCK;

    ---- Fast SPI slave for AVR ---

    nAVR_SPI_REG_ACCESS <= '0' when (bbc_nPGFC = '0' and bbc_A = x"A0") else '1';
    nAVR_SPI_STATUS_REG_ACCESS <= '0' when (bbc_nPGFC = '0' and bbc_A = x"A1") else '1';

    int_avr_INT <= '1' when (elk_TXD_state /= avr_TXD_state_sync) else '0';

    ---- Plus 1 parallel port emulation ----

    nDATA_REG_ACCESS <= '0' when (bbc_nPGFC = '0' and bbc_A = x"71") else '1';
    nSTATUS_REG_ACCESS <= '0' when (bbc_nPGFC = '0' and bbc_A = x"72") else '1';

    ---- Data bus ----

    bbc_D <=
        -- test: return &49 when reading &FDA0
        x"49" when (bbc_nPGFD = '0' and bbc_A = x"A0") else
        -- AVR SPI data
        avr_RXD when (nAVR_SPI_REG_ACCESS = '0' and bbc_RnW = '1') else
        -- AVR SPI status
        "000000" & (elk_TXD_state xnor avr_TXD_state_sync) & (elk_RXD_state xor avr_RXD_state_sync)
            when (nAVR_SPI_STATUS_REG_ACCESS = '0' and bbc_RnW = '1') else
        -- Plus 1 parallel port
        sd_MISO & "0000000" when (nSTATUS_REG_ACCESS = '0' and bbc_RnW = '1') else
        -- default
        "ZZZZZZZZ";

    -- AVR SPI clock domain
    process (int_avr_nSS, int_avr_SCK)
    begin

        -- RISING EDGE of int_avr_SCK: read int_avr_MOSI
        if int_avr_nSS = '1' then

            -- asynchronous reset (must not happen on an int_avr_SCK edge)
            avr_spi_bit_count <= x"0";

        elsif rising_edge(int_avr_SCK) then

            -- increment the count each time
            avr_spi_bit_count <= std_logic_vector(unsigned(avr_spi_bit_count) + 1);

            -- clock in a bit, depending on avr_spi_bit_count
            if avr_spi_bit_count = x"0" then
                -- synchronize elk_RXD_state and elk_TXD_state
                elk_RXD_state_sync <= elk_RXD_state;
                elk_TXD_state_sync <= elk_TXD_state;
            elsif avr_spi_bit_count = x"6" then
                -- SPI is big-endian, so we want to ignore incoming bits 0-5.
                -- bit 6 (1) tells us if the remote wants to send a byte
                avr_spi_receiving <= (
                    int_avr_MOSI -- '1' if the remote has a byte for us
                    and (avr_RXD_state xnor elk_RXD_state_sync) -- '1' if we have room in our buffer
                );
            elsif avr_spi_bit_count = x"7" then
                -- bit 7 (0) tells us if the remote is capable of receiving a byte
                avr_spi_transmitting <= (
                    int_avr_MOSI -- '1' if the remote has buffer space
                    and (avr_TXD_state xor elk_TXD_state_sync) -- '1' if we have a byte to transmit
                );
                -- copy avr_TXD into the shift register if it's safe
                if avr_TXD_state /= elk_TXD_state_sync then
                    avr_spi_SHIFT <= avr_TXD;
                end if;
            elsif avr_spi_bit_count(3) = '1' then
                -- clock in a bit if we have buffer space
                avr_spi_SHIFT <= avr_spi_SHIFT(6 downto 0) & int_avr_MOSI;
                if avr_spi_bit_count = x"F" then
                    if avr_spi_receiving = '1' then
                        avr_RXD_state <= not avr_RXD_state;
                        avr_RXD <= avr_spi_SHIFT(6 downto 0) & int_avr_MOSI;
                    end if;
                    if avr_spi_transmitting = '1' then
                        avr_TXD_state <= not avr_TXD_state;
                    end if;
                end if;
            end if;

        end if;

        -- FALLING EDGE of int_avr_SCK: write int_avr_MISO
        if int_avr_nSS = '1' then

        elsif falling_edge(int_avr_SCK) then

            -- We always update MISO on an int_avr_SCK falling edge.

            if avr_spi_bit_count = x"6" then
                -- '1' if we have a byte to send to the AVR
                int_avr_MISO <= avr_TXD_state xor elk_TXD_state_sync;
            elsif avr_spi_bit_count = x"7" then
                -- '1' if we can accept a byte from the AVR
                int_avr_MISO <= avr_RXD_state xnor elk_RXD_state_sync;
            elsif avr_spi_bit_count(3) = '1' then
                int_avr_MISO <= avr_spi_SHIFT(7);
            end if;
        end if;

    end process;

    -- Electron clock domain
    process (bbc_1MHZE)
    begin
        if falling_edge(bbc_1MHZE) then
            -- AVR SPI registers
            avr_RXD_state_sync <= avr_RXD_state;
            avr_TXD_state_sync <= avr_TXD_state;
            if nAVR_SPI_REG_ACCESS = '0' and bbc_RnW = '0' and elk_TXD_state = avr_TXD_state_sync then
                -- we're writing to the TXD register
                avr_TXD <= bbc_D;
                elk_TXD_state <= not elk_TXD_state;
            end if;
            if nAVR_SPI_REG_ACCESS = '0' and bbc_RnW = '1' and elk_RXD_state /= avr_RXD_state_sync then
                -- the electron just read avr_RXD
                elk_RXD_state <= not elk_RXD_state;
            end if;
            if nAVR_SPI_STATUS_REG_ACCESS = '0' and bbc_RnW = '0' then
                -- we never write to the status register
            end if;

            -- Bit-banged SPI
            if nDATA_REG_ACCESS = '0' and bbc_RnW = '0' then
                -- handle write to &FC71
                bitbang_MOSI <= bbc_D(0);
                bitbang_SCK <= bbc_D(1);
            end if;
        end if;
    end process;

end Behavioural;