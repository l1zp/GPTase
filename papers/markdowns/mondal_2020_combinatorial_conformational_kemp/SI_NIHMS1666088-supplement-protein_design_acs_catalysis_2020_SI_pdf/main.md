# Supporting Information

# Combinatorial Approach for Exploring Conformational Space and Activation Barriers in Computer-Aided Enzyme Design

Dibyendu Mondal, Vesselin Kolev and Arieh Warshel\*

Department of Chemistry, University of Southern California, 3620 McClintock Avenue, Los Angeles, California 90089, United States

\* Email for A. W.: warshel@usc.edu.

# S1. The EVB method

The reaction energy barriers are calculated by means of Empirical Valence Bond method (EVB).1 The theoretical basics of the method are extensively discussed previously.2 Here, we are focusing only on the specific aspects to provide an overview of the method. The reacting system is represented as a superposition of different resonance forms (diabatic states). In that case the potential energy of each state can be represented as a combination of two (or more) force fields – in our case a molecular mechanics (MM) based force field (ENZYMIX)3 and a quantum empirical force field. The diabatic potential energy functions take the explicit form:

$$
\in _ { i } = \alpha _ { g a s } ^ { i } + U _ { i n t r a } ( R , Q ) + U _ { S s } ( R , Q , r , s ) + U _ { s s } ( r , q )
$$

where $R$ and $Q$ denote, respectively, the atomic coordinates and partial charges (the later are calculated using Quantum Mechanical approach) of a fragment of the reaction center (solute) in the $i ^ { \mathrm { { t h } } }$ diabatic state, whereas $r$ and $q$ are the positions, and charges of the rest of the atoms in the system (including the surrounding protein and solvent atoms).

$a _ { g a s } ^ { i }$ is the gas phase energy of the $i ^ { \mathrm { { t h } } }$ diabatic state, wherein all fragments are assumed infinitely separated. Its value can be calculated in a more stringent way,4 but here we implemented parameterization, based on the assumption that it is the same for the reactions in water and protein. $U _ { i n t r a }$ is the intramolecular potential of the solute and it includes the Morse bond potentials. The non-bonding interactions are taken in two separate ways whether pair of atoms: (a) never form bonds in any diabatic states, and (b) form bonds only in one of the diabatic states. $U _ { S s }$ denotes the intermolecular interaction potential between the solute $( S )$ and the surrounding $( s )$ atoms, while $U _ { s s }$ is the potential energy of the interaction between all surrounding atoms (surrounding-surrounding (ss)).

The EVB Hamiltonian, $H _ { E V B }$ , can be defined (in the two-state case) as:

$$
H _ { E V B } = \left[ \begin{array} { l l } { \in _ { i } } & { H _ { i j } } \\ { H _ { i j } } & { \in _ { j } } \end{array} \right]
$$

where the off-diagonal coupling term, $H _ { i j }$ , can be approximated as a function of the reacting bonds, broken either in $i ^ { \mathrm { { t h } } }$ or $j ^ { \mathrm { t h } }$ state. It is also assumed that $H _ { i j }$ is the same in the gas phase, solution, as well as in the protein.

The adiabatic ground-state energy, $E _ { g }$ , and the corresponding eigen vector, $C _ { g }$ , are one solution of the secular equation:

$$
H _ { E V B } C _ { g } = E _ { g } C _ { g }
$$

Since the end-states of the reaction are represented by diabatic states, the system should be moved from the reactant state to the product state in attempt to calculate a complete reaction profile. The EVB free energy surfaces are determined by running MD simulation on a mapping potential, $\epsilon _ { m }$ , that is a linear combination of the diabatic potentials of the starting state of the reaction (state 1), and the final state (state 2). Thus, for a two-state representation of the reaction, the mapping potential takes the form:

$$
\epsilon _ { m } = \lambda _ { m } \epsilon _ { 1 } + \big ( 1 - \lambda _ { m } \big ) \epsilon _ { 2 } \mathrm { , w h e r e } 0 \leq \lambda _ { m } \leq 1
$$

The mapping parameter, $\lambda _ { m }$ , varies between 0 and 1, in $N$ windows, while the system is moving from the initial state to the final state.

The associated change in the free energy can be calculated using free energy perturbation formalism. In that case, the free energy functional at a given $\lambda _ { n }$ , $\Delta G ( \lambda _ { n } )$ , can be defined as:

$$
\Delta G ( \lambda _ { n } ) = \Delta G ( \lambda _ { 0 } \to \lambda _ { n } ) = \sum _ { i = 0 } ^ { N - 1 } \delta G ( \lambda _ { i } \to \lambda _ { i + 1 } )
$$

where

$$
\begin{array} { r } { \delta G ( \lambda _ { i } \to \lambda _ { i + 1 } ) = - \left( \frac { 1 } { \beta } \right) l n \left[ \left. e ^ { \left( - ( \epsilon _ { i + 1 } - \epsilon _ { i } ) \right) \beta } \right. _ { i } \right] } \end{array}
$$

In S6, $\beta = 1 / k _ { B } T ,$ , $k _ { B }$ is the Boltzmann constant, and $T$ is the temperature, kept constant throughout the simulations. The angular bracket $( < > _ { i } )$ operator averages with respect to the mapping potential $\epsilon _ { i }$ .

$\delta G$ represents the free energy change due to the move of the reacting system from reactant state to the final one, when we are simulating on the mapping potential surface, but our aim is to know the ground state free energy change. Thus, the ground state free energy surface $\Delta g ( X ^ { n } )$ , is calculated using the following FEP/US equation:

$$
\exp [ - \Delta \mathrm { g } \bigl ( X ^ { n } \bigr ) \beta ] = \exp [ - \Delta G ( \lambda _ { m } ) \beta ] \bigl \langle \exp [ - ( E _ { g } \bigl ( X ^ { n } \bigr ) - \epsilon _ { m } \bigl ( X ^ { n } \bigr ) ] \beta \bigr \rangle _ { m }
$$

where $X ^ { n }$ is the reaction coordinate, taken in terms of a given energy gap $\epsilon _ { 2 } - \epsilon _ { 1 }$ .

# S2. Initial System preparation and quantum mechanics-based charge calculations

# S2. 1. Haloalkane Dehalogenase

For the Haloalkane dehalogenase (DhlA), the protein $\mathbf { X }$ -ray crystal structure PDB: 2DHC5 was selected as a starting structure. The substrate, dichloroethane $\mathrm { \ C H } _ { 2 } \mathrm { C l } _ { 2 }$ ), is already bound to the protein (in PDB 2DHC). Two diabatic states are used to model the reactant and product states of the reactant center. The charges of the diabatic states of the EVB calculation were taken from our previous computational work.6 As mentioned there, the ESP (the electrostatic potential) charges are calculated by Gaussian,7 using the B3LYP level of theory and $6 { - } 3 1 1 { + } \mathrm { G } ^ { { \ast } { \ast } }$ basis set.

# S2. 2. Kemp eliminase

For the Kemp Eliminase reaction system, PDB:3YND8 of protein HG2 was designated as a starting structure. Protein HG3 has a threonine (T) at $2 6 5 ^ { \mathrm { t h } }$ position of the sequence, in place of serine (S). Thus, the S265 in PDB:3YND was mutated to threonine using Chimera9, based on the DUNBRACK backbone dependent rotamer library.10 The transition state analog 5-nitro benzotriazole is bound to the protein. 5- nitrobenzotriazole is converted to 5-nitro benzisozaxole, before starting the simulations. Two diabatic states are used to model the reactant and product states of the reactant center. In our previous work,11 a special care was taken to calculate the charges of these diabatic states. As we mentioned there, the ab initio free energy surface for the reaction in water can be calculated using mPW1PW91 functional and $6 { - } 3 1 1 \mathrm { G } ^ { { \ast } { \ast } }$ basis set, along with adopting COSMO model for the solvent. The QM charges, obtained from that ab initio calculation, were fitted using restrained electrostatic potential (RESP) procedure to estimate the corresponding RESP based charges for both reactant and product. Those charges of the product state were further modified, based on the transition state charges, obtained from QM calculations (see ref. 11 for more details).

The atoms in the diabatic states (region I) for haloalkane dehalogenase and Kemp eliminase system, are shown in Figs S1 and S2, respectively. All force field parameters (except the charges of the region I atoms of our simulated system) were taken from the ENZYMIX force field ̶ part of the MOLARIS-XG package (version 9.15).12 Specific simulation parameters are provided in Tables S1-S17.

# S3. General Simulation Protocol

The center of the region I was defined as a center of the simulated system. Subsequently, the system was immersed in a water sphere with radius of $1 8 \mathrm { ~ \AA ~ }$ (the center of the sphere and the center of the simulation system both coincide). All water molecules at the boundary of the sphere were subject to polarization and radial restraint, according to the surface constraint all-atom solvent (SCAAS) model.13 The SCAAS surface constraints allow to treat a finite system as if it is part of an infinite system and the local reaction field (LRF) approach14 treats the long-range effects therein. The protonation state of the ionizable residues for both systems was determined by means of Monte Carlo Proton Transfer (MCPT)15 calculations, performed by the MOLARIS-XG software (version 9.15). For Kemp eliminase, all ionizable residues within $1 0 \textup { \AA }$ of the system center were explicitly ionized. In the case of DhlA, all residues within $1 0 \mathrm { \AA }$ of the system center (except for E56) were explicitly ionized. The reason for not ionizing E56 is discussed in details in our previous work.6

Initially, the simulated systems were gradually heated from 10 up to $3 0 0 K$ , for 200 ps, using 1 fs time step (fixed region I). Afterwards, the last frame of the heating simulation was set an input for a new, 200 ps long relaxation, during which the constraint upon the region I was gradually decreased. The last frame of thus obtained trajectory was employed as an initial structure for running yet another, 100 ps long relaxation, imposing 0.3 kcal/mol position constraint on region I, and $0 . 0 3 \mathrm { k c a l / m o l }$ on the protein atoms outside region I. Those parameters were kept fixed throughout the EVB calculations.

S4. New protein structure generation using the ‘rotamer generation’ MODULE in MOLARIS-XG software

# S4. 1. Haloalkane dehalogenase (DhlA)

The protocol implemented for generating rotamers for each mutating residue is already described in the main text. For the DhlA system, the relaxed structures (of the wild type protein) employed by the relaxation protocol (see section S3), are used as a reference for generating all single and doubly mutated protein structures by MOLARIS-XG software (version 9.15). In case of doubly mutated structure, the first mutated residue was randomly picked out. As mentioned in the main text, the order of introducing the mutations does not considerably affect the simulation results. The generated mutated structures had their potential energy minimized, by means of the Steepest descent method. That process was carried out until the fluctuation of the energy reached certain low amplitude, or until its absolute value started showing a saturation. The structures obtained as a result of the energy minimization were later used during the EVB simulations.

# S4. 2. Kemp eliminase

Simulation protocol, similar to the one introduced for haloalkane dehalogenase (section S4. 1.), has been implemented here. It should be noted that the same structure generation protocol (as described in section S4. 1.) is used everywhere in the current work. Note that the energy minimizations of the generated structures take place once all mutations are introduced upon the reference structure. To estimate how the order of introducing the mutations may affect the results, we performed a test simulation. In that test simulation, four different paths (A, B, C and D) were suggested for mutating three residues in the protein HG3.b (see main text). At every stage related to a position along the pathways, A, B, and C (Fig 5), the corresponding structures were generated by performing a single mutation, then minimized and used in EVB calculations, except for pathway D, where all three mutations were introduced at once. For pathways A, B, and C, the structure corresponding to the minimum activation barrier is taken as a reference structure to support the next round of single mutation.

In all cases of new structure generation, the rotamer generation module in MOLARIS-XG software (version 9.15) is called from within specially designed Python and Bash scripts to manage the structure generations. A link to a git repository is given at the end of the SI to provide access to all scripts and input files used to generate new protein structures.

# S5. EVB simulations

The EVB method was employed to calculate the free energy barrier of the reactions. The corresponding free energy profiles were calculated by using the Free Energy Perturbation/Umbrella Sampling (FEP/US) approach, where the total FEP simulation was divided into 21 frames, each 20 ps long (1 fs time step for the integration). Another series of FEP simulations, based on 31 frames, each one 20 ps long, was also performed for selected initial cases, and the results were compared to those previously obtained for 21 frames. Since no significant difference in the results was found, we implemented the initially suggested mapping schema - the one based on 21 frames - to all subsequent simulations. Finally, the results were verified by performing several independent runs and comparing the computed numbers.

In both cases, the EVB simulations were calibrated with respect to the water reactions. The calibration parameters are those in Table S8 and S17, obtained for DhlA and Kemp eliminase system, respectively.

# S6. Practical Simulation Protocol

Overall, the simulation was performed in two stages: (a) new protein structure generation, and (b) EVB simulation to calculate the activation free energies of the reaction. The initial system setup described in section S2 was the first step of our simulations. We then prepared the simulation system (described in section S3) by: (a) identifying region I of the simulation system and introducing the EVB force field for this region, as well as the ENZYMIX force field for the rest of the system; (b) by introducing the solvent sphere and boundary conditions; and (c) defining the ionizible residues in the system. Following the protocol, the simulation system was thoroughly relaxed (see section S3) before adopting it as a base for new protein structure generation. In the case of dehalogenase, the next step is the generation of new protein structures as described in section S4. 1. Since only single and double mutation cases are considered in the dehalogenase system, the treatment of more mutations is discussed below (in the case of Kemp eliminase). The EVB simulation (see section S5) was followed by the new structure generation stage. Finally, the results obtained from the EVB calculation were processed to obtain the data given in Table 1.

In the case of Kemp eliminase, the protein structure generation and EVB calculations were repeated multiple times to move from one sequence to another. We used there the relaxed structure, as described in section S3, to perform the first set of structure generation for protein HG3 (mutating at sequence positions with residues same as it is in the reference structures). The protocol of the EVB simulations that were performed afterwards are summarized in section S5. It should be noted that the structure corresponding to the minimum activation free energy $\Delta G _ { m i n } ^ { \neq }$ in eq 1) is used for further protein structure generation. For proteins $_ { \mathrm { H 3 . 3 b } }$ to HG3.17, the protein structure generation were carried out by taking the structure corresponds to the minimum activation free energy $( \Delta G _ { m i n } ^ { \neq } )$ as reference and EVB simulation protocol was kept the same, following the details given in section S5. Even though limited mutation-based simulation protocol was implemented for protein HG3.14 and HG3.17, the new structure generation and EVB simulation protocol were performed the same way as before. The only extra part added for HG3.14 and HG3.17 was a prediction step. In the prediction step, all possible single and double mutations were performed based on a reference structure and the EVB simulations were performed next. The results obtained from those EVB simulations were explored to predict a small number of starting structures of the probable mutants. The starting structures of the mutants were then generated by using the new protein structure generation protocol, followed by EVB calculations to obtain the activation free energies.

The protein structure generation and EVB simulations were both controlled by the execution of Python and Bash scripts (not part of the simulation software Molaris-XG). Similarly, the prediction steps mentioned above (for HG3.14 and HG3.17), were also managed by running a Python code. One can access the code of the scripts, along with relevant input files at https://github.com/dibyendu92/In-silico-Enymze-deisgn.

![](images/4330768bdde9c3fe6a3b139d6af90de028077d8b52c784a1d1618cd98a3b8c7b.jpg)
Figure S1. Illustration and characterization of the atoms in the reaction region of DhlA. The numbering scheme is valid for the EVB region (region I of the simulation system), and the atoms are color-coded (C $=$ green, $\mathrm { H } = \mathrm { b l a c k }$ , $\mathrm { O } =$ red and $\mathrm { C l } = \mathrm { p i n k } ,$ ). The C(5)-Cl(7) bond is the cleaving bond.

Table S1. Partial atomic charges and atom types for the reactant and product state

![Table 1](images/1ad453810ac63d5dfac30ed2f81123c2ff484c012c82be727a10b9dca282b5d6.jpg)

Table S2. Morse bond parameters

![Table 2](images/46bffc9de4e264761a31505cc017bf37583648b490b60d9a618506e823a2cffa.jpg)

$$
V _ { b } = D _ { M } \big [ 1 - e ^ { - \mu ( b - b _ { 0 } ) ^ { 2 } } \big ]
$$

Table S3. Bond angle parameters

![Table 3](images/c59dbd00ec95b4374c7e512e08f0110ec2c4b6a6a77869a707f1047bdf46d52b.jpg)

$$
V _ { \theta } = k _ { \theta } ( \theta - \theta _ { 0 } ) ^ { 2 }
$$

Table S4. Proper dihedral parameters

![Table 4](images/6fd828dca9feed73a07a49cb307905ee2ab745f5b2dc3e4f52aaa3d98cb40917.jpg)

$$
V _ { \varphi } = k _ { \varphi } [ 1 + c o s ( n \varphi - \varphi _ { 0 } ) ]
$$

![Table 5](images/6e2ce0fa074c003d73c76adc5def03361ed09db3ea7e70cb9fe39f7f43450d16.jpg)

Table S5. Improper dihedral parameters

![Table 6](images/dc66e6cfd8e0cf676f63c35d8c59cbe49130f14407136b40d295935d4c55e7dd.jpg)

$$
V _ { \varphi } = k _ { \varphi } [ 1 + c o s ( n \varphi - \varphi _ { 0 } ) ]
$$

Table S6. Nonbonded parameters (EVB pair-wise parameters for atoms bonded in one of the EVB states)

![Table 7](images/813544436a777929b7a8404fd35aa1c39a5485fcdaf79a9838102dd28dbaf2f5.jpg)

$$
V _ { n b } = C e ^ { - \alpha r }
$$

![Table 8](images/e85bb5c1aaf6daf810274792fcc57ec8b87ecdba2ec1c6b47ad0c28d92db0be3.jpg)

# Table S7. Nonbonded Parameters (EVB atom wise parameters for atoms never bonded)

$$
V _ { n b } ^ { i j } = \frac { A _ { i } \cdot A _ { j } } { r _ { i j } ^ { 1 2 } } - \frac { B _ { i } \cdot B _ { j } } { r _ { i j } ^ { 6 } }
$$

Table S8. Other EVB parameters

![Table 9](images/375f29a0e1de4fa48fcefc3a82d830e40c2b3f187bbe71e82b7f71cdc1bd97ef.jpg)

![Table 10](images/d3d7ba5d1269fe0d2050be9b06658ba85961d5df6e0b1ead782264e56897cbf2.jpg)

![Table 11](images/0b5bc41bedb7da96a4757a826be134122f4ffea27b85c3a160b0ece46dca98a7.jpg)

![](images/822b462321f0eb68c97ef6418b37d2deefd72eccd964232074e5c24af07c2d6a.jpg)
Figure S2. Illustration and characterization of the atoms in the reaction region of the Kemp eliminase reaction. The numbering scheme corresponds to the EVB region (region I of the simulation system). The atoms are color-coded ( $\mathrm { H } { = } ]$ black, $\mathrm { O = }$ red and $\mathbf { N } { = }$ blue). C(3)-H(14) and O(1)-N(2) are the bonds to be broken and N(2)-C(3) is the one converted to a triple bond.

Table S9. Partial atomic charges and atom types for the reactant and product state

![Table 12](images/35a91a035260a609b0d646442b6fe62681ad0eda3cd11e7a84093d84edd71d75.jpg)

Table S10. Morse bond parameters

![Table 13](images/e2883e0c81a682a6ec4db35b9b319fa9d8afef4982a0f399ac77c44e4a71c3c2.jpg)

$$
V _ { b } = D _ { M } \big [ 1 - e ^ { - \mu ( b - b _ { 0 } ) ^ { 2 } } \big ]
$$

Table S11. Bond angle parameters

![Table 14](images/b25fc5e046779aeb77943d1feed42b0c425192ed99c5595c9c6b466f25e61499.jpg)

\*RS– Reactant state; PS– Product state

$$
V _ { \theta } = k _ { \theta } ( \theta - \theta _ { 0 } ) ^ { 2 }
$$

Table S12. Proper dihedral parameters

![Table 15](images/264c776aebde965975877589e8d5ce6cf69adac5a64b3f21a823ee9f99d777f1.jpg)

$\ast _ { \mathrm { R S - } }$ Reactant state; PS– Product state

$$
V _ { \varphi } = k _ { \varphi } [ 1 + c o s ( n \varphi - \varphi _ { 0 } ) ]
$$

Table S13. Improper dihedral parameters

![Table 16](images/d2010c05d4d0cfc4704340e3d2dbf1be0771285f26268950a667ca14baa1e5ed.jpg)

$$
V _ { \varphi } = k _ { \varphi } [ 1 + c o s ( n \varphi - \varphi _ { 0 } ) ]
$$

Table S14. Nonbonded parameters (EVB pair-wise parameters for atoms bonded in one of the EVB states)

![Table 17](images/0622fce843e2993f79cd77dfb3e1037a75cdae1912ba98a7f2af61e1774df35f.jpg)

$$
V _ { n b } = C e ^ { - \alpha r }
$$

![Table 18](images/d191c98f487630f72b038dbe108cad339ef9c5529c5707c826e10873021a7b56.jpg)

$$
V _ { n b } ^ { A B } = \sqrt { C _ { A } \cdot C _ { B } } e ^ { - \sqrt { \alpha _ { A } \cdot \alpha _ { B } \cdot } r _ { A B } }
$$

Table S15. Nonbonded parameters (EVB atom wise parameters for atoms bonded in one of the EVB states)

![Table 19](images/d13e73e372c4cac697909e718b2805d12a2fa3b520145cb656a084772b6cac57.jpg)

# Table S16. Nonbonded Parameters (EVB atom wise parameters for atoms never bonded)

$$
V _ { n b } ^ { i j } = \frac { A _ { i } \cdot A _ { j } } { r _ { i j } ^ { 1 2 } } - \frac { B _ { i } \cdot B _ { j } } { r _ { i j } ^ { 6 } }
$$

Table S17. Other EVB parameters

![Table 20](images/b3d94b1035f6e3d7bed9d60ba7f2196ee7daed069e98cecf76e6cf16b4644b1d.jpg)

![Table 21](images/10804012a17493f54ba757aaa7ad1971088f449d53f8d151e46ea22b2dc2a234.jpg)

\*rAB – distance between C(3) and H(14); rBC – distance between H(14) and C(15)

# References

1. Warshel, A.; Weiss, R. M., An Empirical Valence Bond Approach for Comparing Reactions in Solutions and in Enzymes. J. Am. Chem. Soc. 1980, 102 (20), 6218-6226.
2. Kamerlin, S. C. L.; Warshel, A., The empirical valence bond model: theory and applications. Wires Comput Mol Sci 2011, 1 (1), 30-45.
3. Lee, F. S.; Chu, Z. T.; Warshel, A., Microscopic and Semimicroscopic Calculations of Electrostatic Energies in Proteins by the Polaris and Enzymix Programs. J. Comput. Chem. 1993, 14 (2), 161-185. 4. Aqvist, J.; Fothergill, M.; Warshel, A., Computer-Simulation of the Co2/Hco3- Interconversion Step in Human Carbonic Anhydrase-I. J. Am. Chem. Soc. 1993, 115 (2), 631-635.
5. Verschueren, K. H. G.; Seljee, F.; Rozeboom, H. J.; Kalk, K. H.; Dijkstra, B. W., Crystallographic Analysis of the Catalytic Mechanism of Haloalkane Dehalogenase. Nature 1993, 363 (6431), 693-698. 6. Jindal, G.; Slanska, K.; Kolev, V.; Damborsky, J.; Prokop, Z.; Warshel, A., Exploring the challenges of computational enzyme design by rebuilding the active site of a dehalogenase. Proc. Natl. Acad. Sci. U. S. A. 2019, 116 (2), 389-394.
7. Frisch, M. J.; Trucks, G. W.; Schlegel, H. B.; Scuseria, G. E.; Robb, M. A.; Cheeseman, J. R.; Scalmani, G.; Barone, V.; Mennucci, B.; Petersson, G. e., Gaussian∼ 09 Revision D. 01. 2014.
8. Privett, H. K.; Kiss, G.; Lee, T. M.; Blomberg, R.; Chica, R. A.; Thomas, L. M.; Hilvert, D.; Houk, K. N.; Mayo, S. L., Iterative approach to computational enzyme design. Proc. Natl. Acad. Sci. U. S. A. 2012, 109 (10), 3790-3795.
9. Pettersen, E. F.; Goddard, T. D.; Huang, C. C.; Couch, G. S.; Greenblatt, D. M.; Meng, E. C.; Ferrin, T. E., UCSF chimera - A visualization system for exploratory research and analysis. J. Comput. Chem. 2004, 25 (13), 1605-1612.
10. Shapovalov, M. V.; Dunbrack, R. L., A Smoothed Backbone-Dependent Rotamer Library for Proteins Derived from Adaptive Kernel Density Estimates and Regressions. Structure 2011, 19 (6), 844- 858.
11. Frushicheva, M. P.; Cao, J.; Chu, Z. T.; Warshel, A., Exploring challenges in rational enzyme design by simulating the catalysis in artificial kemp eliminase. Proc. Natl. Acad. Sci. U. S. A. 2010, 107 (39), 16869- 16874.
12. Warshel, A.; Chu, Z.; Villa, J.; Strajbl, M.; Schutz, C.; Shurki, A.; Vicatos, S.; Plotnikov, N.; Schopf, P., Molaris-XG, v 9.15. University of Southern California: Los Angeles 2012.
13. Warshel, A.; King, G., Polarization Constraints in Molecular-Dynamics Simulation of Aqueous-Solutions - the Surface Constraint All Atom Solvent (Scaas) Model. Chem. Phys. Lett. 1985, 121 (1-2), 124- 129.
14. Lee, F. S.; Warshel, A., A Local Reaction Field Method for Fast Evaluation of Long-Range Electrostatic Interactions in Molecular Simulations. J. Chem. Phys. 1992, 97 (5), 3100-3107.
15. Vicatos, S.; Rychkova, A.; Mukherjee, S.; Warshel, A., An effective Coarse-grained model for biological simulations: Recent refinements and validations. Proteins 2014, 82 (7), 1168-1185.
