from typing import Self

import h5py
import matplotlib.figure
import numpy
from matplotlib.figure import Figure
from numpy.typing import NDArray


class VaspDataError(Exception):
    pass


class VASPData:
    def __init__(self, energies: NDArray[float], forces: NDArray[float], positions: NDArray[float]):

        # main quantities:
        self.energies = energies
        self.forces = forces
        self.positions = positions

    @classmethod
    def from_h5(cls, path: str) -> Self:
        with h5py.File(path, 'r') as f:
            # fetch data
            ion_dynamics = f['intermediate/ion_dynamics']

            energies = ion_dynamics['energies'][()]
            forces = ion_dynamics['forces'][()]
            positions = ion_dynamics['position_ions'][()]

            if '/input/poscar/selective_dynamics_ions' in f:
                # remove forces for non-selected DOF, as they may have a large force that is not taken into account
                mask = f['/input/poscar/selective_dynamics_ions'][()]
                pos_mask = numpy.where(mask == 0)
                forces[:, pos_mask] = .0

            return cls(energies, forces, positions)

    def make_graph(self, energy_label: int = 1) -> matplotlib.figure.Figure:
        # compute derived quantites to be plotted
        min_energy = numpy.min(self.energies[:, energy_label])
        dE = self.energies[1:, energy_label] - self.energies[:-1, energy_label]

        force_intensities = numpy.linalg.norm(self.forces, axis=2)

        forces_rms = numpy.sqrt(numpy.mean(force_intensities ** 2, axis=1))
        forces_max = numpy.max(force_intensities, axis=1)

        displacements = self.positions[1:] - self.positions[:-1]
        displacement_intensities = numpy.linalg.norm(displacements, axis=2)
        displacements_rms = numpy.sqrt(numpy.mean(displacement_intensities ** 2, axis=1))
        displacements_max = numpy.max(displacement_intensities, axis=1)

        ddisps = self.positions[1:] - self.positions[0]
        ddisps_intensities = numpy.linalg.norm(ddisps, axis=2)
        ddisps_sum = numpy.sum(ddisps_intensities, axis=1)

        # plot it
        X = numpy.arange(0, self.energies.shape[0])
        X2 = numpy.arange(1, self.energies.shape[0])
        fig = Figure(figsize=(6, 6), dpi=100)

        # 1. Energy
        ax = fig.add_subplot(311)
        ax.set_ylabel('Energy (eV)')
        ax.grid(axis='y')

        ax.plot(X, self.energies[:, energy_label] - min_energy, 'b-', label='Energies')

        secax = ax.twinx()
        secax.set_ylabel('|ΔE| (eV)')
        secax.set_yscale('log')

        secax.plot(X2, numpy.abs(dE))

        # 2. forces
        ax = fig.add_subplot(312)
        ax.set_ylabel('Forces (eV/Å)')
        ax.set_yscale('log')
        ax.grid(axis='y')

        ax.plot(X, forces_rms, 'g-', label='RMS')
        ax.plot(X, forces_max, 'r-', label='Max')

        ax.legend()

        # 3. disps
        ax = fig.add_subplot(313)
        ax.set_xlabel('steps')
        ax.set_ylabel('Displacements (Å)')
        ax.set_yscale('log')
        ax.grid(axis='y')

        ax.plot(X2, displacements_rms, 'g-', label='RMS')
        ax.plot(X2, displacements_max, 'r-', label='Max')

        ax.legend()

        secax = ax.twinx()
        secax.set_ylabel('|p[i]-p[0]| (Å)')

        secax.plot(X2, ddisps_sum)

        return fig
