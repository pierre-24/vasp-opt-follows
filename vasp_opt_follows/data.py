from typing import Self, Tuple

import h5py
import matplotlib.figure
import numpy
from matplotlib.figure import Figure
from numpy.typing import NDArray


class VASPDataError(Exception):
    pass


class VASPData:
    def __init__(self, energies: NDArray[float], forces: NDArray[float], positions: NDArray[float], lattice_vectors: NDArray[float]):

        # main quantities:
        self.energies = energies
        self.forces = forces
        self.positions = positions
        self.lattice_vectors = lattice_vectors

        # compute derived quantities
        self.min_energy = numpy.min(self.energies)
        self.delta_e = self.energies[1:] - self.energies[:-1]

        self.force_intensities = numpy.linalg.norm(self.forces, axis=2)
        self.forces_rms = numpy.sqrt(numpy.mean(self.force_intensities ** 2, axis=1))
        self.forces_max = numpy.max(self.force_intensities, axis=1)

        self.displacements = self.positions[1:] - self.positions[:-1]
        self.displacement_intensities = numpy.linalg.norm(self.displacements, axis=2)
        self.displacements_rms = numpy.sqrt(numpy.mean(self.displacement_intensities ** 2, axis=1))
        self.displacements_max = numpy.max(self.displacement_intensities, axis=1)

        self.lattice_vectors_norm = numpy.linalg.norm(self.lattice_vectors, axis=2)
        self.cell_volumes = numpy.array([numpy.linalg.det(x) for x in self.lattice_vectors])

    @classmethod
    def from_h5(cls, path: str, energy_label: int = 1) -> Self:
        """Fetch data in a HDF5 file.

        TODO: stress tensor
        """
        with h5py.File(path, 'r') as f:
            # fetch data
            ion_dynamics = f['intermediate/ion_dynamics']

            energies = ion_dynamics['energies'][()][:, energy_label]
            forces = ion_dynamics['forces'][()]
            positions = ion_dynamics['position_ions'][()]
            lattice_vectors = ion_dynamics['lattice_vectors'][()]

            if '/input/poscar/selective_dynamics_ions' in f:
                # remove forces for non-selected DOF, as they may have a large force that is not taken into account
                mask = f['/input/poscar/selective_dynamics_ions'][()]
                pos_mask = numpy.where(mask == 0)
                forces[:, pos_mask] = .0

            return cls(energies, forces, positions, lattice_vectors)

    def make_graphs(self) -> Tuple[matplotlib.figure.Figure, matplotlib.figure.Figure]:
        """Get the "energy" (energy + forces) graph and the "position" (position + lattice vectors) grap"""

        # plot it
        X = numpy.arange(0, self.energies.shape[0])
        X2 = numpy.arange(1, self.energies.shape[0])

        # "energy" graph:
        fig_energy = Figure(figsize=(6, 6), dpi=100)

        # -- ENERGY
        ax = fig_energy.add_subplot(211)
        ax.set_ylabel('Energy (eV)')
        ax.grid(axis='y')

        ax.plot(X, self.energies - self.min_energy, 'b-', label='Energies')

        secax = ax.twinx()
        secax.set_ylabel('|ΔE| (eV)')
        secax.set_yscale('log')

        secax.plot(X2, numpy.abs(self.delta_e))

        # --- FORCES
        ax = fig_energy.add_subplot(212)
        ax.set_ylabel('Forces (eV/Å)')
        ax.set_xlabel('steps')
        ax.set_yscale('log')
        ax.grid(axis='y')

        ax.plot(X, self.forces_rms, 'g-', label='RMS')
        ax.plot(X, self.forces_max, 'r-', label='Max')

        ax.legend()

        # "position" graph:
        fig_position = Figure(figsize=(6, 6), dpi=100)

        ddisps = self.positions[1:] - self.positions[0]
        ddisps_intensities = numpy.linalg.norm(ddisps, axis=2)
        ddisps_sum = numpy.sum(ddisps_intensities, axis=1)

        # --- DISPLACEMENTS
        ax = fig_position.add_subplot(211)
        ax.set_ylabel('Displacements (Å)')
        ax.set_yscale('log')
        ax.grid(axis='y')

        ax.plot(X2, self.displacements_rms, 'g-', label='RMS')
        ax.plot(X2, self.displacements_max, 'r-', label='Max')

        ax.legend()

        secax = ax.twinx()
        secax.set_ylabel('|p[i]-p[0]| (Å)')

        secax.plot(X2, ddisps_sum)

        # --- LATTICE
        ax = fig_position.add_subplot(212)
        ax.set_xlabel('steps')
        ax.set_ylabel('Norm of lattice vectors (Å)')
        ax.plot(X, self.lattice_vectors_norm[:, 0], 'r-', label='a')
        ax.plot(X, self.lattice_vectors_norm[:, 1], 'g-', label='b')
        ax.plot(X, self.lattice_vectors_norm[:, 2], 'b-', label='c')

        secax = ax.twinx()
        secax.set_ylabel('Volume (Å³)')
        secax.plot(X, self.cell_volumes)

        ax.legend()

        return fig_energy, fig_position
