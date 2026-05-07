# Supporting Information

# Protein Flexibility and Preorganization in the Design of Enzymes. The Kemp Elimination Catalysed by HG3.17

K. Świderek,1 I. Tuñón,1 V. Moliner,2 J. Bertrán3

1. Departament de Química Física, Universitat de València, 46100 Burjasot, (Spain) 2. Departament de Química Física i Analítica; Universitat Jaume I, 12071 Castellón (Spain)
3. Departament de Química; Universitat Autònoma de Barcelona, 08193 Bellaterra, (Spain)

# Monomer A

![](images/63556a5ad87d41852399f659961d5e4dd58e9ac2d0fdf6b38490e1a3356db4f9.jpg)

# Monomer B

![](images/ca91f267ded2eb3b5ee568f398b12de7a1007f03b40a2ba89d448f76bf323f3b.jpg)
Figure S1. Time dependent RMSD computed for the $\mathrm { C - C a - N }$ atoms of the backbone of monomer A and monomer B during the 2 ns of MD simulations.

Monomer A

![](images/a588e00bf628ee12cf5f616c9221817048a842a0c8e7957468d2297cb40cc803.jpg)
Monomer B
Figure S2. Time dependent evolution of substrate-protein key distances along the 2 ns MD simulations on monomer A and monomer B in the reactant state.

![](images/4ee026fda20bb02ab299d53c89af74ccc146af1438f5838834d6dc50875e42bd.jpg)
Figure S3. ChelpG atomic charges of substrate and inhibitor computed at M06-2X/6- $3 1 + ( \mathsf { d } , \mathsf { p } )$ level in gas phase and in solution (SMD continuum model).

![](images/f36b6e955b12e54355429655430cf256417a92655a9309f227b56257ea7d4ea9.jpg)
Figure S4. Schematic representation of optimized TS and reactant complex structures in monomer A and monomer B obtained at the AM1/MM level. Distances are reported in $\mathrm { \AA }$ .

![](images/0b4b900d9d9714b806f03cd03ff066c6cd318c4ccb9719749a61aee3248611d3.jpg)
Figure S5. Schematic representation of TS geometries obtained in aqueous solution. Results are based on calculations with the SMD continuum model and with a QM/MM model at the $\mathrm { M 0 6 { - } 2 X / 6 { - } 3 1 { + } ( d , p ) / M M }$ level. Distances are reported in $\mathrm { \AA }$ .

Table S1. Total transmission coefficients $( \Gamma )$ computed as the product of the dynamic recrossing (γ) and tunnelling (κ) transmission coefficients at $\mathrm { T } = 3 0 0 \mathrm { K }$ . See below for computational details.

![Table 1](images/58ccc30a811a110030935208b5d614a48d2453598986d33820c788bec3248e60.jpg)

Table S2. CHELP Charges on key atoms computed in reactant complex and in TS of monomer A and monomer B computed at the M06-2X/MM level. Charges computed in solution in reactants correspond to separated species.

![Table 2](images/644b125bc07aa108cacf8f70b369f36b21015a83a7081f6ecd35b3d0a546c308.jpg)

acharges computed for Michaelis complex; bseparated reactants in water; c oxygen acceptor atom of transferred proton

# Optimizing structures on the AM1/MM and M06-2X/MM potential energy surfaces

The procedure was performed in two active sites, using initial protein configurations of the two different monomers of the 4BS0 dimer after 2 ns of MD simulations, monomer A and B, respectively. Potential energy surfaces (PESs) were obtained scanning two distinguished reaction coordinates: (a) the antisymmetric combination of distances defining the proton transfer from the substrate to Asp127 $( \xi _ { 1 } = { \mathrm { d } } ( \mathrm { C l } { \mathrm { - H } } ) - { \mathrm { d } } ( \mathrm { H } - { }$ OD2Asp127)) and (b) the distance defining the ring opening process $( \xi _ { 2 } = \mathrm { d } ( \mathrm { N } 2 { \cdot } \mathrm { O } 3 ) )$ .

A micro-macro iteration optimization algorithm1,2 was used to localize, optimize, and characterize the saddle points - TS and minima - RC and PC structures using a Hessian matrix containing all the coordinates of the QM subsystem, whereas the gradient norm of the remaining movable atoms was maintained less than $0 . 5 \mathrm { k J } { \cdot } \mathrm { m o l } ^ { - 1 } { \cdot } \mathring { \mathrm { A } } ^ { - 1 }$ . The lbfgsb optimization algorithm was used to optimize the QM subsystem with a gradient tolerance $1 . 0 \ \mathrm { \ k J { \cdot } m o l { } ^ { - 1 } { \cdot } \ell ^ { - 1 } }$ , while for the MM subsystem the conjugate gradient algorithm was selected. IRC paths were traced from the located TS at both levels of theory. After minimization of the full system, those residues lying more than $2 0 \textup { \AA }$ apart of any of the substrate atoms was kept frozen in the remaining calculations.

# Tunneling and Transmission coefficients calculations

Deviations from classical Transition State Theory (TST) as a result of quantumtunneling and dynamical recrossings effects can be estimated by means of the inclusion of a prefactor in the expression of the rate constant: 3,4,5

$$
k _ { r } ( T S T ) = r \cdot \frac { k _ { B } T } { h } e ^ { \left[ - \frac { A G _ { _ { Q C } } } { R T } \right] }
$$

Where $\mathbf { k } _ { \mathrm { B } }$ is the Boltzmann constant, $\mathrm { T }$ the temperature, h the Planck constant, $\mathrm { R }$ the constant of ideal gases , $4 G _ { a c t } ^ { Q C }$ is the quasiclassical activation free energy and $\Gamma$ the generalized transmission coefficient, is obtained as the product of recrossing (γ) and tunneling $( \kappa )$ contributions:

Recrossing transmission coefficients $\gamma$ were computed $\gamma$ using the ‘‘positive flux’’ formulation6 that assumes that the trajectories are initiated at the barrier top with forward momentum along the reaction coordinate. Then for a given reaction time, t, the time-dependent transmission coefficient is defined as:

$$
\gamma ( t ) = \frac { \left. j _ { + } \theta \left[ \xi ( t + t ) \right] - j _ { + } \theta \left[ \xi ( t - t ) \right] \right. } { \left. j _ { + } \right. }
$$

where $\xi$ is the reaction coordinate, $j _ { + }$ represents the initially positive flux at $\mathrm { \Delta t } = 0$ , given by $\xi ~ ( \mathfrak { t } = 0 )$ , and $\theta \left( \xi \right)$ is a step function equal to one in the product side of the reaction coordinate and zero on the reactant side. 99 TS structures selected from the maximum along the Minimum Free Energy Path traced along the 2D-PMFs were used as the starting points for the free downhill trajectories. Initial velocities were assigned from a Maxwell-Boltzmann distribution corresponding to $3 0 0 \mathrm { K }$

The equations of motion were integrated to positive times, where the obtained velocities were multiplied by one, and to negative times, the velocities were multiplied by minus one. The simulations were extended from $^ { - 1 }$ to $+ 1$ ps, using a time step of 0.2 fs and the microcanonical thermodynamical collective (NVE), using the velocity Verlet algorithm. The trajectories obtained can be classified as reactive, when they connect reactants to products (RP), or nonreactive, when they connect reactants to reactants (RR) or products to products (PP). These later trajectories account for barrier recrossings. From the 99 computed free downhill trajectories, the time dependent transmission coefficient is calculated by means of eq (S3).

The tunneling transmission coefficients, κ, were calculated with the small-curvature tunneling (SCT) approximation, which includes reaction-path curvature appropriate for enzymatic hydrogen transfers.7,8,9

(1) Turner, A. J.; Moliner, V.; Williams, I. H. Phys. Chem. Chem. Phys. 1999, 1, 1323-1331.
(2) Martí, S.; Moliner, V.; Tuñón, I. J. Chem. Theory Comput. 2005, 1, 1008-1016.
(3) Alhambra, C.; Corchado, J.; Sánchez, M. L.; Garcia-Viloca, M.; Gao, J.; Truhlar, D. G. J. Phys. Chem. B 2001, 105, 11326-11340.
(4) Truhlar, D. G.; Gao, J. L.; Alhambra, C.; Garcia-Viloca, M.; Corchado, J.; Sánchez, M. L.; Villa, J. Acc. Chem. Res. 2002, 35, 341-349.
(5) Truhlar, D. G.; Gao, J.; Garcia-Viloca, M.; Alhambra, C.; Corchado, J.; Luz Sanchez, M.; Poulsen, T. D. Int. J. Quantum Chem. 2004, 100, 1136-1152.
(6) Bergsma, J.P.; Gertner, B.J.; Wilson, K.R.; Hynes, J.T. J. Chem. Phys. 1987, 86, 1356-1376.
(7) Pu, J.; Gao, J.; Truhlar, D. G. Chem. Rev. 2006, 106, 3140-3169.
(8) Pang, J.; Pu, J.; Gao, J.; Truhlar, D. G.; Allemann, R. K. J. Am. Chem. Soc. 2006, 128, 8015-8023.
(9) Garcia-Viloca, M.; Truhlar, D. G.; Gao, J. Biochemistry 2003, 42, 13558-13575.
