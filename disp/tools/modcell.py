"""
Tools for bespoke modification of cell files
"""
import re
from typing import List
from pathlib import Path
import ase


def replace_block(lines: List[str],
                  block_name: str,
                  block_pattern: str,
                  new_value: List[str],
                  check=True) -> List[str]:
    """
    Replace the blocks in a list of lines with new values
    """
    in_block = False
    out_from_block = False
    new_lines = []
    for line in lines:
        if re.search(r'%BLOCK ' + f'{block_pattern.upper()}', line.upper()):
            in_block = True
            new_lines.append('%BLOCK ' + block_name.upper())
            new_lines.extend(new_value)
            new_lines.append('%ENDBLOCK ' + block_name.upper())
            continue
        if re.search(r'%ENDBLOCK ' + f'{block_pattern.upper()}',
                     line.upper()) and in_block:
            out_from_block = True
            in_block = False
            continue
        if not in_block:
            new_lines.append(line)
    # Not inside the block - attach the lines
    if out_from_block is False and in_block is False and check:
        raise RuntimeError(f'Did not found start of the block {block_name}')
    if out_from_block is False and in_block is True:
        raise RuntimeError(f'Did not found end of the block {block_name}')
    return new_lines


def modify_cell(base_cell: str, atoms: ase.Atoms):
    """Modify the cell file using the structure given by the ``atoms``, leaving only stuff unchanged."""
    cell_lines = []
    cell = atoms.cell
    for i in range(3):
        cell_lines.append(
            f'{cell[i, 0]:.10f} {cell[i, 1]:.10f} {cell[i, 2]:.10f}')

    pos = atoms.positions
    pos_lines = []
    for symbol, i in zip(atoms.get_chemical_symbols(), range(pos.shape[0])):
        pos_lines.append(
            f'{symbol}  {pos[i, 0]:.10f} {pos[i, 1]:.10f} {pos[i, 2]:.10f}')

    base_lines = Path(base_cell).read_text().split('\n')

    # Replace the cell and the symbols
    new_lines = replace_block(base_lines, 'POSITIONS_ABS',
                              'POSITIONS_(FRAC|ABS)', pos_lines)
    new_lines = replace_block(new_lines, 'LATTICE_CART', 'LATTICE_(CART|ABC)',
                              cell_lines)

    return new_lines
