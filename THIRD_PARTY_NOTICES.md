# Third-party notices

## Tatiana chess pieces

The SVG files in `src/wizard_chess/gui/assets/pieces/tatiana/` are the **Tatiana** chess piece
set created by **sadsnake1** and distributed by the Lichess project.

- Source: <https://github.com/lichess-org/lila/tree/master/public/piece/tatiana>
- License: [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International][cc]
- Changes: none

The artwork remains subject to that license, including its attribution, non-commercial, and
share-alike conditions. Wizard Chess is not affiliated with or endorsed by Lichess.

[cc]: https://creativecommons.org/licenses/by-nc-sa/4.0/

## Stockfish 18

Wizard Chess distributes an unmodified official **Stockfish 18** Linux x86-64 baseline
executable. It is stored with XZ compression and extracted to the user's cache on first use.

- Upstream project: <https://github.com/official-stockfish/Stockfish>
- Release: <https://github.com/official-stockfish/Stockfish/releases/tag/sf_18>
- Exact source-and-binary archive:
  <https://github.com/official-stockfish/Stockfish/releases/download/sf_18/stockfish-ubuntu-x86-64.tar>
- License: GNU General Public License version 3 or later
- Changes to the executable: none
- Distribution-only change: recompressed with `xz -1`
- Official tar SHA-256: `5c6f38b02a4da5f3ffe763f27da6c3e743eebefd92b50cb3661623b96696adff`
- Executable SHA-256: `7a44d64fd877ee888a5160349827563444e1935ca6c1095d0f8e0859d57101c7`
- Bundled XZ SHA-256: `785c19e66634a1758122cda70be1ea770ca308119fbe3b502bbe3facca628be4`

The exact upstream archive contains both the distributed executable and its complete
corresponding source. Wizard Chess also includes Stockfish's `Copying.txt`, `AUTHORS`, and
upstream `README.md` beside the bundled platform directory. Stockfish remains a separate UCI
process and is not affiliated with or endorsed by Wizard Chess.
