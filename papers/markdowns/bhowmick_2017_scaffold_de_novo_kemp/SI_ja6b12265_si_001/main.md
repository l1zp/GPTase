# The Importance of the Scaffold for de Novo Enzymes: A Case Study with Kemp Eliminase

Asmit Bhowmick, Sudhir C. Sharma and Teresa Head-Gordon

Parameterization of substrate in reactant and transition state. In order to perform simulations with 5-nitrobenzisoxazole using the AMOEBA force field, we need to obtain parameters for all atoms in the substrate molecule in the reactant and transition states. For parameterizing the transition state of this molecule, the structure of the substrate used for parameterization was reported in Ref $[ ^ { 1 } ] .$ , in which the C-H and N-O bonds are partially broken and the C-N bond is somewhere between a double and triple bond as shown in Figure 2 of the main text. Since the transition state structure is not at it’s energy minimum, we do not minimize the structure as done in the original protocol (the reactant state structure is minimized). As can also be seen in Figure 1 of the main text, the system used for the parameterization includes not only the ligand but also a base (acetate) to better model the transition state. The overall system has a net charge of -1e.

We then use the protocol described by Ponder and Ren $[ ^ { 2 } ]$ which has 2 main components – first finding the electrostatic parameters and second, finding ‘valence’ parameters (bond lengths, bond angles, dihedrals). The electrostatic component is described briefly in 6 steps below.

1. Run a single point quantum mechanics-based calculation on the transition state structure using Gaussian ${ \tt g 0 9 }$ at the MP2/6-311G(1D, 1P) level of theory. This calculation returns the electron density as obtained at this relatively low level of theory.
2. Find approximate charges, dipoles and quadrupoles by running the distributed multipole analysis using GDMA on the electron density.
3. Once we have the approximate multipoles, use Tinker’s POLEDIT program to break the dipole moments into permanent contributions that act between polarization groups and mutual contributions that act within and between polarization groups.
4. A second Gaussian ${ \tt g 0 9 }$ calculation is run at the MP2/6-311G(2D, 2P) level of theory to obtain a electrostatic potential.
5. In order to obtain a electrostatic potential, we create a spatial grid on which to calculate the potential using Tinker’s POTENTIAL program and then compute the potential using the Gaussian CUBEGEN program.

6. Finally, using Tinker’s POTENTIAL program, we fit the atomic multipoles to the MP2/6-311G(2D, 2P) electrostatic potential.

After finishing the first step, the ‘valence’ parameters are assigned from similar, previously parameterized organic compounds. Thus, we model the transition state of the substrate with transition state electrostatics and energy minimized state valence parameters.

The exact same protocol was used to parameterize the EL state of the 19NT inhibitor for the ketosteroid isomerase enzyme.

Calculation of dipole moment of the 3 bonds in EL and EL† states for 5-nitrobenzisoxazole. We used the monopoles and dipole moments of the parameterized 5-nitrobenzisoxazole in AMOEBA to calculate the dipole moment of the 3 bonds in each state. Table S2 lists the parameters used to calculate the dipole moment of each bond. The positive direction is as shown in Fig 2 of the main text. Since the net charge is not zero, we used $\Delta \mathsf { q }$ instead of q to calculate the dipole contribution from the monopoles.

Active site residues for KE07, KE70 and KSI. We defined active site residues to be residues that
are within $5 \textup { \AA }$ from the substrate of the respective enzymes studied. The residue numbers are -
KE07: 9, 11, 48, 50, 101, 128, 169, 201, 202
KE70: 16, 18, 45, 48, 72, 103, 138, 140, 168, 202, 204
KSI: 16, 20, 40, 57, 61, 66, 86, 88, 90, 99, 101, 103, 116, 118, 120

# TABLES

Table S1. Design and laboratory directed evolution mutations for KE07 and KE70. The computationally designed residues (red), mutated residues introduced by LDE of a given round (black) and residues after which insertions took place (green) have been listed in the table below 3 4

![Table 1](images/d6e318f9e9179d426dced97b20bf72544f96c83800943bc67ca757b178f3401d.jpg)

Table S2. Bond dipoles using AMOEBA force field electrostatics.

![Table 2](images/ec54ed861748e37b7c1615acb626555d10683bff57e68e5b5cdee8074b127d3f.jpg)

Table S3: Contributions of pre-organization relative to reorganization to the free energy stabilization of the transition state along the 3 bonds of the substrate 5-nitrobenzisoxazole in the EL and $\operatorname { E L } ^ { \dag }$ states of KE07 and KE70 designed enzymes and best LDE variants. We evaluate the preorganization with an adiabatic step whereby the transition state dipoles change, but there is no relaxation of the structural ensemble to these changes, using the reactant state ensemble only. See Table 1 in the text for further details.

![Table 3](images/55be291839dddde025d588a8cd27f2444d80d8cfc3ce518bcde762d6bf47834e.jpg)

Table S4: List of top residues that contribute ${ > } 1 0  { \mathrm { ~ M V / c m } }$ electric field by magnitude at the C-H, C-N, and NO bond in either the EL and EL† states for the designed enzyme KE07 enzyme and the best LDE R7 variant. Positive sign indicates field supporting bond breaking (C-H and N-O) and bond-making (C-N). Contributions to activation free energies are also provided using the dipole values reported in Table S2

![Table 4](images/649633386303be9e08c075cffbcff11d61e4a80944aca78491ecbeef56e7e4c1.jpg)

![Table 5](images/5d96ff5ce147eb7dad191d146fad5638b2ae810f78dadcaea413f37330605917.jpg)

![Table 6](images/a7ad1a09c97d592d52ba23adc9a29ae3faa7901ac0b3bb781debab3e5189291b.jpg)

Table S5: List of top residues that contribute ${ > } 1 0  { \mathrm { ~ M V / c m } }$ electric field by magnitude at the C-H, C-N, and NO bond in either the EL and EL† states for the designed enzyme KE70 enzyme and the best LDE R6 variant. Positive sign indicates field supporting bond breaking (C-H and N-O) and bond-making (C-N). Contributions to activation free energies are also provided using the dipole values reported in Table S2

![Table 7](images/0170fd272025f86b231c7829d897c09e8c31b0bd4194a1ce2bdea53bf8c8db23.jpg)

![Table 8](images/cadb25c654f1424251108e3a4029f139375400293f60d6da4a38ec9421f52c2f.jpg)

![Table 9](images/3f9e7b0a862274206fa83b179443b5f4a96cf07f756a514b3d6f1839c9a5a6c2.jpg)

Table S6: Chemical Positioning vs. Electric Field Environment at the C-H, C-N and O-N Bonds. The magnitude of the electric field in either the EL and EL† states for the designed KE07 enzyme and the best R7 variant. The active site is defined by residues within $5 \mathrm { ~ \AA ~ }$ from the center of the substrate, while the protein environment (scaffold) is summed over all residues outside this region. Solvent includes waters in the neck of the TIM barrel as well as the surrounding hydration and bulk water. Sum of free energy are summed over all bonds, with dominant region and bond most affected shown. Positive sign indicates field supporting bond breaking. Fields are reported in units of $\mathbf { M V } / \mathrm { c m }$

![Table 10](images/8edbd4cefa7cd1741d16c7aca5e11e9ca4046a08711f42d1cb75972045b8c5f4.jpg)

![Table 11](images/9dad18b140cf1351a039f1b7af30b10934111a068cef9d50184bdb208f13914c.jpg)

![Table 12](images/5295314bd19e71ef7dabb924541efffcdf6502fb83cf764a71283f5e66951df5.jpg)

![Table 13](images/5b37c3cb4560d5ad2a56c696cbe4c8f085a9b181758e84eb660db4faa614a98b.jpg)

Table S7: Chemical Positioning vs. Electric Field Environment at the C-H, C-N and O-N Bonds. The magnitude of the electric field in either the EL and $\operatorname { E L } ^ { \dag }$ states for the designed KE70 enzyme and the best R6 variant. The active site is defined by residues within $5 \mathrm { ~ \AA ~ }$ from the center of the substrate, while the protein environment is summed over all residues outside this region. Solvent includes waters in the neck of the TIM barrel as well as the surrounding hydration and bulk water. Sum of free energy are summed over all bonds, with dominant region and bond most affected shown. Positive sign indicates field supporting bond breaking. Fields are reported in units of $\mathbf { M V } / \mathrm { c m }$

![Table 14](images/528c87b566f194b24a539686c23343fc9dc1b9175a25b3c931d6fbc1b293c396.jpg)

![Table 15](images/29f68967fda13187c9fd4ba27dd681ef6202d1f5e83db58687eed2fd6ec050ee.jpg)

![Table 16](images/cfc1f0ac3e9f9f1dd02590a4325c4e17f4b63767e0d4fc1fcecd99a801a1d5ab.jpg)

![Table 17](images/1e230c7cb689aaff74cbd73c1500abf7ce6c9561a6e01b7480dbc9ec77d744b6.jpg)

Figure S1. The Kemp elimination KE07 and KE70 designs. (a) KE07 involved residues mutated from the original scaffold (red) as well as mutations introduced by LDE shown in blue. (b) KE70 involved residues mutated from the original scaffold (red) as well as mutations made during laboratory DE shown in blue. Additional design mutations via a recombination DE strategy are shown in green.

![](images/3c56df7cfce94aef3a57892d03a290c7b17b19ed098fc837be333916d234de39.jpg)

# REFERENCES

1. Hu, Y.; Houk, K. N.; Kikuchi, K.; Hotta, K.; Hilvert, D., Nonspecific Medium Effects Versus Specific Group Positioning in the Antibody and Albumin Catalysis of the Base-Promoted Ring-Opening Reactions of Benzisoxazoles. Journal of the American Chemical Society 2004, 126 (26), 8197-8205.
2. Ren, P.; Wu, C.; Ponder, J. W., Polarizable Atomic Multipole-Based Molecular Mechanics for Organic Molecules. J Chem Theory Comput 2011, 7 (10), 3143-3161.
3. Khersonsky, O.; Röthlisberger, D.; Dym, O.; Albeck, S.; Jackson, C. J.; Baker, D.; Tawfik, D. S., Evolutionary Optimization of Computationally Designed Enzymes: Kemp Eliminases of the Ke07 Series. J. Mol. Bio. 2010, 396, 1025-42.
4. Khersonsky, O.; Röthlisberger, D.; Wollacott, A. M.; Murphy, P.; Dym, O.; Albeck, S.; Kiss, G.; Houk, K. N.; Baker, D.; Tawfik, D. S., Optimization of the in-Silico-Designed Kemp Eliminase Ke70 by Computational Design and Directed Evolution. J. Mol. Bio. 2011, 407, 391-412.
