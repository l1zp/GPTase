Supporting Information for:

Enhancing a De Novo Enzyme Activity by Computationally-Focused, Ultra-Low-Throughput Sequence Screening

Valeria A. Risso,1 Adrian Romero-Rivera,2 Luis I. Gutierrez-Rus,1 Mariano Ortega-Muñoz,3
Francisco Santoyo-Gonzalez,3 Jose A. Gavira, 4 Jose M. Sanchez-Ruiz, \*,1 Shina C. L. Kamerlin\*,2

1. Departamento de Química Física, Facultad de Ciencias, University of Granada, 18071- Granada, Spain
2. Science for Life Laboratory, Department of Chemistry-BMC, Uppsala University, BMC Box 576, S-751 23 Uppsala, Sweden
3. Departamento de Química Organica, Facultad de Ciencias, University of Granada, 18071- Granada, Spain
4. Laboratorio de Estudios Cristalograficos, Instituto Andaluz de Ciencias de la Tierra, CSIC-University of Granada, Avenida de las Palmeras 4, Granada 18100 Armilla, Spain

# Table of Contents

# Supplementary Figures… . S4

Figure S1. Root mean square deviations during equilibration of simulations of the GNCA4-WT and of variants with single amino acid substitutions ..S4 Figure S2. Root mean square deviations during equilibration of simulations of the twenty FuncLib variants.. …..S5 Figure S3. Root mean square deviations during equilibration of simulations of the crystal structures of the three FuncLib variants . S6 Figure S4. Kemp eliminase activity of 522 clones from a random library on the de novo GNCA4-WT $\beta$ -lactamase.. …S6 Figure S5. Plots of Kemp eliminase activity vs. substrate concentration for FuncLib variants………S7 Figure S6. Correlation between calculated and experimental activation free energies for the Kemp elimination of 5-nitrobenzisoxazole by the GNCA4-WT and a series of active site mutants… ..S8 Figure S7. Correlation between calculated energetics and experimental activation free energies for the Kemp elimination of 5-nitrobenzisoxazole by the GNCA4-WT and the top twenty variants predicted from the FuncLib webserver ..S9 Figure S8. Electrostatic contributions of individual residues to the calculated activation free energies for the Kemp elimination of 5-nitrobenzisoxazole by the top 20 best scoring GNCA4 variants predicted by FuncLib… ..S10 Figure S9. Correlation between geometric parameters and calculated and experimental activation free energies and experimentally measured kinetics… S11 Figure S10. Comparison of the X-ray and FuncLib predicted structures of the GNCA4-2 variant….S12

# Supplementary Tables … . S13

Table S1. Sequence space explored after diversification of 11 active site residues by the FuncLib webserver.. …S13 Table S2. Ionized residues and protonation patterns of histidine residues during EVB simulations of the $\beta$ -lactamase catalyzed Kemp elimination of 5-nitrobenzisoxazole. ...S14 Table S3. Percentage acetonitrile used at different substrate concentrations… …S14 Table S4. Data collection and refinement statistics of the 3D structural models.. . S15

Table S5. Rosetta scores and calculated and experimental activation free energies for the GNCA4-WT $\beta$ -lactamase, as well as the top twenty variants predicted from FuncLib.. . S16 Table S6. Amino acid substitutions introduced in the twenty top-ranked FuncLib variants… ..S17 Table S7. Average donor-acceptor (D-A) distances and donor-hydrogen-acceptor (D-H…A) angles obtained from EVB simulations of different experimentally characterized variants of the GNCA4-WT $\beta$ -lactamase. S18 Table S8. Average donor-acceptor (D-A) distances and donor-hydrogen-acceptor (D-H…A) angles obtained from EVB simulations of the GNCA4-WT $\beta$ -lactamase, as well as of the top twenty variants predicted from FuncLib. S19

Supplementary References … …S20

# Supplementary Figures

![](images/5a95c3015e10bd865eb524d7f6fc3bc4068b69430ec3b175740a5e7693d3ec07.jpg)

Figure S1. The root mean square deviations (RMSD, Å) of all backbone atoms of the GNCA4-WT and single amino acid substitutions used for the calibration of our EVB model, at the approximate EVB transition state $\Lambda = 0 . 5$ ) for the Kemp elimination reaction catalyzed by these enzymes. Data was collected every 10 ps from the initial equilibration runs, and is shown as averages and standard deviations over ten individual 20 ns MD simulations per system (i.e. 200 ns cumulative simulation time per system). The average RMSD per system is denoted by solid blue lines, and the standard deviations per point over all trajectories are illustrated by the shaded area on each plot.

![](images/fc458d74cf40d527622316fcb64c9a5b4c8a7ae1f677c4cca1fecd5e80a64b50.jpg)

Figure S2. The root mean square deviations (RMSD, Å) of all backbone atoms of the twenty FuncLib variants studied in this work (computationally predicted structures), at the approximate EVB transition state $( \lambda = 0 . 5 )$ for the Kemp elimination reaction catalyzed by these enzymes. Data was collected every 10 ps from the initial equilibration runs, and is shown as averages and standard deviations over ten individual 20 ns MD simulations per system (i.e. 200 ns cumulative simulation time per system). The average RMSD per system is denoted by solid blue lines, and the standard deviations per point over all trajectories are illustrated by the shaded area on each plot.

![](images/b9f533681398770f909934dc2b4d624ce05041d724727f58cfe885e2f7924f23.jpg)

Figure S3. The root mean square deviations (RMSD, Å) of all backbone atoms of the three FuncLib variants studied in this work for which crystal structures are available, at the approximate EVB transition state $\lambda =$ 0.5) for the Kemp elimination reaction catalyzed by these enzymes. Data was collected every 10 ps from the initial equilibration runs, and is shown as averages and standard deviations over ten individual 20 ns MD simulations per system (i.e. 200 ns cumulative simulation time per system). The average RMSD per system is denoted by solid blue lines, and the standard deviations per point over all trajectories are illustrated by the shaded area on each plot.

![](images/98e44b96f059e168960c2e153340db00a2a2ece13f746ecba92d38f1d5fb35ca.jpg)

Figure S4. The Kemp eliminase activity of 522 clones from a random library prepared on the de novo GNCA4-WT $\beta \mathrm { . }$ -lactamase (mutational load 3-5 mutations). The activity of these clones is shown relative to the activity of the background enzyme (shown as a black horizonal line). The grey horizontal lines represent the standard deviation interval for the background variant derived from measurements performed on 52 clones.

![](images/36232aac62861bdec53c313ca15d1c6ad2855fb8ba3c8148a3670443c8a65420.jpg)
Figure S5. Plots of Kemp eliminase activity vs. substrate concentration at (left) pH 7 and (right) $\mathrm { p H } 8 . 4$

Activities for the background protein (GNCA4-WT), as well as the 4 variants that display substantially enhanced catalysis at both pH values are found in Figure 2. Shown here are the activities of the GNCA4- WT and the remaining 16 variants from the top 20 variants from the FuncLib prediction (Table S5). The lines are the best fits of the Michaelis-Menten equation.

![](images/7598a5450d5831b61061184401f9a3f584e6fac037e069416bf55cf801a8b87a.jpg)

Figure S6. Correlation between calculated and experimental activation free energies for the Kemp elimination of 5-nitrobenzisoxazole by the GNCA4-WT and a series of active site mutants, calculated using linear regression analysis. The raw data for this figure is shown in Table 2. The correlation between the calculated and experimental activation free energies, calculated using linear regression analysis, is -0.46. Note that the differences in energies for each system are so small, that even very small thermodynamic differences can lead to weaker correlation with the experimental values.

![](images/6a3856ee535053cd60111d2ed2fe0f2b7787819428a0554160d7fa0aa829babb.jpg)

Figure S7. Correlation between (A) the Rosetta score from FuncLib and the experimental activation free energies $( \Delta \mathrm { G ^ { \ddagger } } _ { \exp } )$ , $\mathbf { \left( B \right) }$ the activation free energies calculated using the structure predictions from FuncLib $( \Delta \mathrm { G } _ { \mathrm { ~ c a l c , F L } } ^ { \ddagger } )$ and $\Delta \mathrm { G } _ { \mathrm { ~ \small { ~ e x p } } } ^ { \ddagger }$ , and (C) the activation free energies calculated directly from crystal structures, where available, and $\Delta \mathrm { G } _ { \mathrm { ~ } \exp } ^ { \ddagger }$ . The raw data for this figure can be found in Table S5. Note that, for consistency, we did not include the GNCA4-WT in the correlation calculations for panels (A) and $\mathbf { \left( B \right) }$ , as this is not a FuncLib predicted variant. As can be seen, in terms of the correlation between the calculated and experimental values, there is a weak correlation between calculated and experimental activation free energies ( $R ^ { 2 } = 0 . 2 7$ , calculated using linear regression analysis, note that we have removed the GNCA4- WT from this correlation as this is not a FuncLib predicted structure). This is, however, due to the fact that the energy differences involved are, from a computational perspective, so small that even small deviations from the experimental value will lead to weak correlation with experiment. In terms of the comparison between the Rosetta score obtained from FuncLib (Table S4) and the experimental activation free energy, we obtain essentially no correlation with experiment $R ^ { 2 } = 0 . 1 2$ , again omitting the GNCA4-WT for the same reason as above), which likely reflects the fact that the FuncLib ranking does not include any information about the substrate or transition state, and is based exclusively on the stability of the scaffold.1 Similarly, for the variants where we have crystal structures available (GNCA4-WT, GNCA4-2, GNCA4- 12 and GNCA4-19), we obtain similar correlation between calculated and experimental activation free energies $R ^ { 2 } = 0 . 3 8 )$ , although this is a correlation over only 4 enzyme variants, and the energy difference between the calculated and experimental values is always within ${ \sim } 1 \ \mathrm { k c a l { \cdot } m o l { \cdot } } 1$ of the experimental value, indicating again that the weak correlation coefficients in this specific case are mainly due to the very small energy differences involved (which are within the resolution of EVB and other QM/MM methodologies as described in the main text), rather than a problem with the method.

![](images/f9913c733ca98934ea0cb03a52716eea8f650223c1b12fdf95f1795a716694c1.jpg)
Figure S8. The electrostatic contributions of individual residues to the calculated activation free energies

(∆∆G‡elec) for the Kemp elimination of 5-nitrobenzisoxazole by the top 20 best scoring GNCA4 variants predicted by FuncLib. 1 All values were obtained by applying the linear response approximation (LRA)2, 3 to the calculated EVB trajectories, as in our previous works, 4-6 and scaled assuming a dielectric constant of 4 for the highly hydrophobic environment of the de novo active site of this $\beta \mathrm { . }$ -lactamase (Figure 1). Note that the deviations observed for residue 256 are due to the mutation of this residue (Table S1).

![](images/d9cef78603feb694bf59943b396ecb16ca0cc7d9d177835fcb59f5015b11f19d.jpg)

Figure S9. Correlations between the calculated and experimental activation free energies and the (A, C) donor-acceptor (D-A) distances $( \mathrm { \AA } )$ and $( \mathbf { B } , \mathbf { D } )$ donor-hydrogen-acceptor (D-H…A) angles ${ \bf \Pi } ^ { ( \circ ) }$ in our EVB simulations, calculated based on the data presented in Tables 2, 3, S5, S7 and S8, using linear regression analysis. Correlations between the geometric parameters and (A, B) calculated activation free energies or $( { \bf C } , { \bf D } ) \log k _ { \mathrm { c a t } } / K _ { \mathrm { M } }$ are shown here for all variants considered in this work, both single-point mutations and FuncLib predictions, with the exception of the GNCA4-4 variant, which is an outlier in the data as shown in Figure 9. (E) Schematic overview of the orientation of the reacting fragments in the wild-type enzyme. The annotated distance and angle are the average values from our EVB simulations of the wild-type enzyme (Tables S7 and S8).

![](images/e45af87e27b7fdb1e969306122fe9eb5a9b11db53d36e47f21f0d6eecb239b8d.jpg)
Figure S10. Overlay of the crystal structures of the GNCA4-2 variant obtained via (blue) X-ray crystallography (PDB ID: 6TY6) and (tan) FuncLib prediction.

# Supplementary Tables

Table S1. Sequence space explored after diversification of 11 active site residues by the FuncLib webserver. 1

![Table 1](images/6533b3db374b5353b6e4909c3dd7c3b981f964c223c1bb48b0d890fe52314d3d.jpg)

Table S2. List of ionized residues as well as the protonation patterns of histidine residues in EVB simulations of the $\beta$ -lactamase catalyzed cleavage of 5-nitrobenzisoxazole via Kemp elimination. a

![Table 2](images/8ec1e90ae7e068ac5a7df3e4e1344c069532181299fa3b7e2c8b1a2b52a27d8b.jpg)

a All residues not listed here were kept in their unionized forms during the simulations, as they fell outside the explicit simulation sphere (see the Methodology section of the main text). Protonation states and numbering based on residue numbering in PDB ID: 5FQK. 7

Table S3. Percentage acetonitrile (%ACN) used during kinetic measurements at different substrate concentrations.

![Table 3](images/29c14440343ea1cb184ff54c9d22847a5c42b23f8a7635def819f2b42e2f3713.jpg)

Table S4. Data collection and refinement statistics of the 3D structural models.a

![Table 4](images/c38efac55fc5685bad1690ea305d73cbeedda51b9935d07eaa820e5b0fb38887.jpg)

a Statistics for the highest-resolution shell are shown in parentheses.

Table S5. Rosetta scores8 and calculated and experimental activation free energies for the GNCA4-WT $\beta$ - lactamase, as well as the top twenty variants predicted from FuncLib.a

![Table 5](images/7f98701d02c787947b7ac2bc96ac1f3e2b3794ac7f0f5d8248f34764a6a248bd.jpg)

a The GNCA4-WT $\beta$ -lactamase, which is used as the baseline for our study, is referred to in this table as “wild-type” (“GNCA4-WT”). Experimental activation free energies $( \Delta \mathrm { G ^ { \ddagger } e x p } )$ were derived from $k _ { \mathrm { c a t } }$ , where available, based on kinetic data presented in Tables 2 and 3 (note that all calculations were performed without a His-tag, and therefore kinetic data from Table 2 was used for the GNCA4-WT). Calculated activation free energies $\Delta G _ { \mathrm { \mathrm { ~ c a l c , X T L } } } ^ { \dot { \mathrm { ~ } } }$ if calculated based on an available crystal structure, and $\mathrm { \Delta \Delta \mathrm { G ^ { \ddagger } } } _ { \mathrm { c a l c , F L } }$ if calculated based on the structure predicted by FuncLib) are presented as average values and standard error of the mean over thirty independent EVB trajectories per system. The $\Delta \Delta \mathrm { G ^ { \ddagger } }$ values represent the difference between the experimental activation free energy and the calculated activation free energy based on crystal structures or structures obtained from FuncLib, respectively. All energies are presented in kcal·mol-1 . ‘-’ indicates ‘data not available’. For the full list of FuncLib1 predictions, see the Supplementary Data.

Table S6. Amino acid substitutions introduced in the twenty top-ranked FuncLib1 variants.

![Table 6](images/1218a71e7bc14689eb0a5c62793ec0f315cafa2e3308a83173bbb60714d354f0.jpg)

Table S7. Average donor-acceptor (D-A) distances and donor-hydrogen-acceptor (D-H…A) angles obtained from EVB simulations of different experimentally characterized variants of the GNCA4-WT $\beta \mathrm { . }$ - lactamase.a

![Table 7](images/4820ff92c7ddcde488563242a156f91936f204d1ca3b6b6550bb8beacb80c404.jpg)

a D-A distances are presented in $\textrm { \AA }$ and D-H..A angles are presented in °. Data is shown as average values and standard deviations over 30 independent trajectories. MC, TS and PC denote the Michaelis complex, transition state, and product complex, respectively.

Table S8. Average donor-acceptor (D-A) distances and donor-hydrogen-acceptor (D-H…A) angles obtained from EVB simulations of the GNCA4-WT $\beta$ -lactamase, as well as of the top twenty variants predicted from FuncLib.a

![Table 8](images/bc5d79a40678919c3d5c096762d792f44a6868d1cdf89a19025745fa1da14021.jpg)

a D-A distances are presented in $\textrm { \AA }$ and D-H..A angles are presented in °. Data is shown as average values and standard deviations over 30 independent trajectories. MC, TS and PC denote the Michaelis complex, transition state, and product complex, respectively.

1. O. Khersonsky, R. Lipsh, Z. Avizemer, Y. Ashani, M. Goldsmith, H. Leader, O. Dym, S. Rogotner, D. L. Trudeau, J. Prilusky, P. Amengual-Rigo, V. Guallar, D. S. Tawfik and S. J. Fleishman, Mol. Cell, 2018, 72, 178-186.e175.
2. F. S. Lee and A. Warshel, J. Chem. Phys., 1992, 97, 3100.
3. I. Muegge, H. Tao and A. Warshel, Protein Eng. Des. Sel., 1997, 10, 1363-1372.
4. Y. S. Kulkarni, Q. Liao, D. Petrović, D. M. Krüger, B. Strodel, T. L. Amyes, J. P. Richard and S. C. L. Kamerlin, J. Am. Chem. Soc., 2017, 139, 10514-10525.
5. Y. S. Kulkarni, Q. Liao, F. Byléhn, T. L. Amyes, J. P. Richard and S. C. L. Kamerlin, J. Am. Chem. Soc., 2018, 140, 3854-3857.
6. Y. S. Kulkarni, T. L. Amyes , J. P. Richard and S. C. L. Kamerlin, J. Am. Chem. Soc., 2019, 141, 16139-16150.
7. V. A. Risso, S. Martinez-Rodriguez, A. M. Candel, D. M. Krüger, D. Pantoja-Uceda, M. Ortega-Muñoz, F. Santoyo-Gonzlez, E. A. Gaucher, S. C. L. Kamerlin, M. Bruix, J. A. Gavira and J. M. Sanchez-Ruiz, Nat. Commun., 2017, 8, 16113.
8. A. V. Morozov and T. Kortemme, Adv. Protein Chem., 2005, 72, 1-38.
