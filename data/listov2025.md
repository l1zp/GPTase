# Complete computational design of high-efficiency Kemp elimination enzymes

https://doi.org/10.1038/s41586-025-09136-2

Received: 25 January 2025

Accepted: 9 May 2025

Published online: 18 June 2025

Open access

Check for updates

Dina Listov<sup>1</sup>, Eva Vos<sup>2</sup>, Gyula Hoffka<sup>3,4</sup>, Shlomo Yakir Hoch<sup>1</sup>, Andrej Berg<sup>5</sup>, Shelly Hamer-Rogotner<sup>6</sup>, Orly Dym<sup>6</sup>, Shina Caroline Lynn Kamerlin<sup>2,3</sup> & Sarel J. Fleishman<sup>1*</sup>

Until now, computationally designed enzymes exhibited low catalytic rates $^{1-5}$  and required intensive experimental optimization to reach activity levels observed in comparable natural enzymes $^{5-9}$ . These results exposed limitations in design methodology and suggested critical gaps in our understanding of the fundamentals of biocatalysis $^{10,11}$ . We present a fully computational workflow for designing efficient enzymes in TIM-barrel folds using backbone fragments from natural proteins and without requiring optimization by mutant-library screening. Three Kemp eliminase designs exhibit efficiencies greater than  $2,000 \, \text{M}^{-1} \, \text{s}^{-1}$ . The most efficient shows more than 140 mutations from any natural protein, including a novel active site. It exhibits high stability (greater than  $85^{\circ}\text{C}$ ) and remarkable catalytic efficiency ( $12,700 \, \text{M}^{-1} \, \text{s}^{-1}$ ) and rate ( $2.8 \, \text{s}^{-1}$ ), surpassing previous computational designs by two orders of magnitude $^{1-5}$ . Furthermore, designing a residue considered essential in all previous Kemp eliminase designs increases efficiency to more than  $10^{5} \, \text{M}^{-1} \, \text{s}^{-1}$  and rate to  $30 \, \text{s}^{-1}$ , achieving catalytic parameters comparable to natural enzymes and challenging fundamental biocatalytic assumptions. By overcoming limitations in design methodology $^{11}$ , our strategy enables programming stable, high-efficiency, new-to-nature enzymes through a minimal experimental effort.

Natural enzymes are exceptionally versatile, selective and highly efficient catalysts. Yet, computational design of enzymes that match this proficiency, particularly for non-natural reactions, remains elusive<sup>11</sup>. Recent advances in computational design have enabled rapid and effective optimization of natural enzyme stability, expressibility, catalytic rate and selectivity through fully computational workflows<sup>12,13</sup>. Furthermore, advances in fold design enabled the grafting of natural or engineered active sites into idealized de novo backbones<sup>14,15</sup>. By contrast, enzymes designed de novo, that is, without recourse to naturally occurring enzymes that catalyse the same reaction, were orders of magnitude less active relative to comparable natural ones<sup>1-5,11</sup>. Previous studies have therefore used repeated cycles of laboratory evolution, involving high-throughput screening of mutants, to reach effective enzymes<sup>5-9</sup>. Such cycles are inefficient and are restricted to reactions that can be assayed in medium-to-high-throughput fashion<sup>11</sup>. Critically, continuing to rely on large-library screening of random mutants suggests that our understanding and control of the fundamentals of biocatalysis are far from complete.

The Kemp elimination (KE) reaction (Fig. 1a), a prototype for natural base-catalysed proton abstraction, has long served as a model for studying de novo enzyme design, as no natural enzyme is known to have been evolved for this reaction. Despite increasing sophistication in protein design methods, computationally designed Kemp eliminations exhibited low catalytic efficiencies and rates  $(k_{\mathrm{cat}} / K_{\mathrm{M}}1 - 420\mathrm{M}^{-1}\mathrm{s}^{-1}$  and  $k_{\mathrm{cat}}0.006 - 0.7\mathrm{s}^{-1}$ , respectively) $^{1,3}$  and required further optimization

by iterative mutational library screening to achieve catalytic parameters comparable to or above the median values of enzymes in nature  $(k_{\mathrm{cat}} / K_{\mathrm{M}}10^{5}\mathrm{M}^{-1}\mathrm{s}^{-1},k_{\mathrm{cat}}10\mathrm{s}^{-1})^{16}$

The underlying reasons for the low efficiencies of de novo designed enzymes have been intensely studied $^{10,17-19}$ . These analyses revealed that the designed active sites exhibited significant structural distortions relative to the design conception $^{17,19}$ . Notably, catalysis is extremely sensitive to molecular details, and shifts of the catalytic constellation by a few degrees or tenths of an Ångstrom from optimality may translate into orders of magnitude decreases in efficiency $^{20}$ . Furthermore, designs often exhibited low stability and expressibility $^{7}$ , limiting their ability to accommodate activity-enhancing mutations $^{7,21}$ . Further concerns were that fixed-backbone design methods fail to precisely position non-native catalytic groups $^{1}$ ; the molecular details of the designed transition state (theozyme) were uncertain $^{6,22}$ ; and that protein dynamics $^{23}$  and long-range electrostatic interactions may be necessary to achieve high catalytic efficiency but are unaccounted for in the design process $^{6,24,25}$ .

Recent analyses suggested that overcoming the shortcomings of de novo enzyme design methodology may require artificial intelligence-based approaches, more accurate physics-based energetics and data from high-throughput screening $^{11,26}$ . Here, we test whether recent developments in atomistic protein design that allow accurate backbone $^{27}$  and sequence $^{28,29}$  design in natural protein folds address the limitations of de novo enzyme design methodology without

$^{1}$ Department of Biomolecular Sciences, Weizmann Institute of Science, Rehovot, Israel.  $^{2}$ School of Chemistry and Biochemistry, Georgia Institute of Technology, Atlanta, GA, USA.  $^{3}$ Department of Chemistry, Lund University, Lund, Sweden.  $^{4}$ Department of Biochemistry and Molecular Biology, University of Debrecen, Debrecen, Hungary.  $^{5}$ Department of Chemistry - BMC, Uppsala University, Uppsala, Sweden.  $^{6}$ Structural Proteomics Unit, Weizmann Institute of Science, Rehovot, Israel.  $^{7}$ e-mail: sarel@weizmann.ac.il

![](images/7defbb1380f0e2ab95a17fc1bde14391ff3d48fd0e06a73fda6f6fe3be7153b8.jpg)

![](images/f5110bc6d62d7b04f1822390fc3edf68dd60ba3d025ce2e6b7f5056065ed4f44.jpg)

![](images/6afabee6f3dd5f24301c109291a7e4740759afe8f6681cd9674f7218cc843e51.jpg)  
Fig.1|Key steps in the design workflow. a, KE of 5-nitrobenzisoxazole. 'B' is a base, implemented as the sidechain of Asp or Glu. b, Thousands of backbones are generated through combinatorial backbone assembly (step 1) and stabilized using PROSS $^{29}$  (step 2, red spheres). Geometric matching $^{43}$  and active-site (purple spheres) optimization with Rosetta yield millions of designs that are

resorting to experimental optimization or big-data analyses. To directly compare with previous design approaches, we apply the strategy to the KE reaction and generate enzymes that rival laboratory-evolved eliminases without recourse to high-throughput screening or iterative mutagenesis.

# Designing stability, foldability and activity

Our working hypothesis is that effective enzyme design demands control over all protein degrees of freedom to establish stability, foldability and accurate positioning of the theozyme. Foldability, the ability of the protein to fold uniquely into the design conception, has been a long-standing challenge for de novo enzyme design. Over the past decade, foldability has been partly addressed through de novo fold design, enabling the generation of numerous stable and accurately designed proteins $^{30-33}$ . These design methods, however, maximize foldability, generating backbones that are dominated by ideal secondary structure elements that lack the non-ideal elements that may lower foldability but are nonetheless needed for sophisticated functions $^{12,34}$ . Until now, functionalizing de novo generated folds has produced enzymes that exhibited rates  $(k_{\mathrm{cat}})$  well below  $1\mathrm{s}^{-1}$ . In certain cases, de novo designs

filtered by balancing energy terms that contribute to stability and activity (step 3). A few dozen top designs are chosen for further core (green spheres) and active-site stabilization (step 4). Following experimental screening (step 5), we apply FuncLib $^{28}$  to the active sites of select functional designs (step 6). Illustrations in b (step 5) were created using BioRender (https://biorender.com).

exhibited high catalytic efficiencies  $(10^{4}$  to  $10^{5} \mathrm{M}^{-1} \mathrm{s}^{-1})^{15,35}$  but only through very low  $K_{\mathrm{M}}$  values  $(0.3 - 30 \mu \mathrm{M})$ . Low  $K_{\mathrm{M}}$  values indicate tight binding of the substrate in its ground state, suggesting that the designs optimize molecular recognition of their substrates before the catalytic step. By contrast, turnover numbers  $(k_{\mathrm{cat}})$  reflect the chemical transformation following substrate binding and are a more stringent test of the ability to design high-efficiency catalysts rather than effective binders<sup>36</sup>. The persistently low  $k_{\mathrm{cat}}$  values, including in recent studies<sup>15,35</sup>, highlight the challenge of achieving catalytic control in enzyme design.

Given these limitations, we focused on the TIM-barrel fold, which is one of the most prevalent protein folds found among enzymes $^{37,38}$ . In this fold, the residues of the central  $\beta$  barrel are oriented towards the active-site cavity, providing many opportunities for optimally placing the catalytic and substrate-binding groups. We reasoned that despite the challenges in designing accurate and functional TIM barrels $^{39,40}$ , this fold provides an attractive framework for engineering new enzymatic functions.

We developed a computational method that can be applied, in principle, to any reaction, given a precomputed theozyme. The workflow starts by generating thousands of backbones using combinatorial assembly and design (Fig. 1b, step 1), which combines fragments from

![](images/35b0da8cb0aaa89a2b72b4018051b86d906e69b63f0ad7b7294824b99ec7e072.jpg)  
Fig. 2 | Improving catalytic efficiency through low-throughput screening of FuncLib designs. a, Catalytic efficiencies of 12 FuncLib designs encoding 5-8 active-site mutations relative to Des27. Data represent mean ± s.d. of 2-5 biological replicates, except for Des27.2 and Des27.3 ( $n = 1$ ). b, Michaelis-Menten

![](images/f4ad69ba36b929551934b5fdb4f175549eab86bf9abe956fe0f27b6dd1da07f4.jpg)  
analysis of Des27.7. Data are the mean of two technical repeats. c, The crystal structure of the ligand-unbound Des27.7 (grey, PDB entry 9HVB) verifies the accuracy of the designed active site (blue) with r.m.s.d.  $< 0.5\AA$

![](images/24fe13a745000984da1ea5b26af2797e3ecc75457ea482df7bd3f671d804e921.jpg)

homologous proteins to generate new backbones $^{27,41,42}$ . Subsequently, Protein Repair One Stop Shop (PROSS) design calculations are applied to stabilize the designed conformation $^{29}$  (Fig. 1b, step 2). The resulting structures show backbone variations within the active-site pocket, increasing the likelihood of obtaining foldable backbones that position the theozyme and supporting residues in a catalytically competent and energetically relaxed constellation. Following backbone generation, we implement geometric matching $^{43}$  to position the KE theozyme in each of the designed structures and optimize the remainder of the active site using Rosetta atomistic calculations $^{44}$ , in effect mutating all active-site positions, including the vestigial catalytic residues of the natural enzyme (Fig. 1b, step 3). The workflow results in millions of designs which are filtered using a 'fuzzy-logic' optimization objective function $^{45}$ . This approach balances potentially conflicting objectives that are critical for design of function, such as low system energy and high desolvation of the catalytic base. Selecting a few dozen top-scoring designs, we next stabilize the active site and positions in the protein core $^{46}$  (Fig. 1b, step 4), resulting in designs with more than 100 mutations from any natural protein. Unlike previous approaches, this workflow emphasizes stability across the entire protein. It capitalizes on the ability to generate thousands of stable, natural-like TIM barrels that exhibit backbone diversity in the active site $^{27}$  and on automated scaffold $^{29}$  and active-site $^{28}$  sequence design methods that have been validated on dozens of natural enzymes $^{12}$ .

# Efficient, stable and accurate Kemp eliminations

We applied our pipeline to the indole-3-glycerol-phosphate synthase (IGPS) enzyme family, which can sterically accommodate the 5-nitrobenzisoxazole substrate and was previously used to design Kemp eliminases $^{1,7}$ . The theozyme builds on a catalytic constellation derived from quantum-mechanical calculations $^{47,48}$ . It includes a nucleophile, such as Asp or Glu, which serves as a base for proton abstraction from the substrate, and an aromatic sidechain that forms π-stacking interactions with the substrate in the transition state (Fig. 1b, step 3). The latter interaction has been used in all previous computational Kemp eliminase design studies to promote binding to the aromatic benzisoxazole rings $^{1,3}$ . Typical design studies also introduced a polar interaction with the isoxazole oxygen to stabilize the developing negative charge in the transition state $^{1,3}$ . We excluded this requirement from our theozyme because a water molecule can satisfy it, and a misplaced polar group could reduce reactivity by lowering the  $\mathsf{p}K_{\mathrm{a}}$  of the catalytic base.

We selected 73 designs for experimental testing. The designs ranged from 245 to 268 amino acids and were diverse, with  $30 - 93\%$  sequence identity to one another and  $41 - 59\%$  identity to any natural protein.

In total, 66 designs were solubly expressed and 14 showed cooperative thermal denaturation (Extended Data Fig. 1). Three designs showed measurable KE activity in an initial screen, with the top two designs, Des27 and Des61, exhibiting  $k_{\mathrm{cat}} / K_{\mathrm{M}}$  values of 130 and  $210 \, \mathrm{M}^{-1} \, \mathrm{s}^{-1}$ , respectively, and  $k_{\mathrm{cat}} < 1 \, \mathrm{s}^{-1}$  (Extended Data Fig. 2, Extended Data Table 1 and Supplementary Table 1).

The catalytic rate and efficiency of these designs are on a par with previously designed enzymes $^{1,3}$ , falling short by several orders of magnitude from comparable natural eliminases and from designed Kemp eliminases that were optimized through laboratory-evolution campaigns $^{6,7}$ . To optimize these designs computationally, we applied FuncLib to active-site positions, excluding the theozyme residues. The FuncLib method restricts amino acid mutations to those likely to appear in the natural diversity of homologous proteins $^{28}$ . To develop an optimization strategy for a de novo reaction, we removed all homology-based restrictions in the active site, thus using atomistic energy as the sole optimization objective function. We selected 6 and 12 low-energy designs for experimental testing for Des61 and Des27, respectively, each comprising 5-8 specific mutations relative to their origin. All designs exhibited high expression yields and showed cooperative denaturation (Extended Data Fig. 1 and Supplementary Table 1). One design derived from Des61 showed catalytic efficiency of  $3,600 \mathrm{M}^{-1} \mathrm{s}^{-1}$  and  $k_{\mathrm{cat}}$  of  $0.85 \mathrm{s}^{-1}$ . Remarkably, eight designs on the basis of Des27 showed increased catalytic rates by 10-70-fold (Extended Data Table 1 and Supplementary Table 1), with Des27.7, harbouring seven mutations relative to Des27, reaching  $k_{\mathrm{cat}} / K_{\mathrm{M}} 12,700 \mathrm{M}^{-1} \mathrm{s}^{-1}$  and  $k_{\mathrm{cat}} 2.85 \mathrm{s}^{-1}$ , a rate that is an order of magnitude greater than that of any previously reported computational design $^{3}$  (Fig. 2a,b). This design diverges significantly from natural IGPSs, and a pairwise sequence alignment to the closest protein in the non-redundant sequence database reveals 141 mutations and multiple insertions and deletions (Extended Data Fig. 3). It also diverges in sequence and backbone from previously designed Kemp eliminases in natural IGPS scaffolds $^{1}$  and features a different active-site constellation and position.

We analysed the structural models of Des27 and its FuncLib-derived variants to understand the mechanistic basis for the differences in catalytic efficiency, which span three orders of magnitude, using the Rosetta force field and molecular dynamics (MD) simulations. A sequence alignment of the FuncLib designs shows that Ile136Val, Ile216Val and Val183Ile are associated with high catalytic efficiency (Fig. 3a). Contrasting the structure models of Des27 and Des27.7 reveals that these mutations may increase hydrophobic packing around the catalytic Asp162, probably improving its preorganization and desolvation and increasing its reactivity (Fig. 3a,b, top). Indeed, the Rosetta-computed van der Waals (vdW) energy of Asp162 is highly correlated with catalytic

![](images/e3bf399245fcb3278f61290fd7222520e502ef5e1fd64024ff9eff070de9cc4c.jpg)

![](images/4d4ff52a33f90878fc00b821f35b356476336d1b499692d1ce2743daf130e4cf.jpg)

![](images/c094a3d65a94827a48bcde596d22ecf69543896ca4bf25b33147aa114d6fc69a.jpg)  
Fig. 3|Structural, energetic and dynamic contributions to the improved catalytic rate of Des27.7. a, Mutations (grey background) at positions 136, 216 and 236 trend with increasing catalytic efficiency, which also trends with Rosetta-computed vdW energy of the catalytic Asp162. Spearman  $\rho = -0.88$ ,  $P = 6 \times 10^{-5}$ . b, Analysis of the structural basis of increased KE activity by comparing substrate-bound models of Des27 (left) and Des27.7 (right). c, Percentage of MD simulation time in which the substrate is within the active site for Des27 and Des27.7 (less than or equal to 4 Å between the substrate and the active site centre of mass; blue) or distant from the active site (wheat). For 24% of the time spent in the bound conformation the substrate adopts a reactive donor-acceptor geometry (highlighted arc). The bars on the right of each pie chart show the distribution of conformations (in, out and other) in the reactive mode. d, In MD simulations, 5-nitrobenzisoxazole (sticks) can assume two catalytically

efficiency among the FuncLib designs (Spearman  $\rho = -0.88, P = 6 \times 10^{-5}$ ; Fig. 3a). As further support, MD simulations show that Asp162 is conformationally dynamic in the ligand-unbound models, sampling multiple metastable conformations, and that the fraction of non-productive conformations decreases in Des27.7 relative to Des27 (Extended Data Fig. 4a). Furthermore, the Des27 model suggests that Leu236 may partly overlap with the substrate (Fig. 3b, middle), and that the mutation to Val in Des27.7 would alleviate this unfavourable interaction while increasing the volume of the pocket from 717 to  $829\AA^3$  (Extended Data Fig. 4b,c). Finally, Ile54Val, Phe92His and Leu183Val may improve the solvation of the polar nitro moiety of the substrate (Fig. 3b, bottom), and Phe92His may enable water-mediated polar interactions with the nitro group. Thus, although the seven mutations in Des27.7 are mostly conservative, their aggregate markedly improves the catalytic parameters by reshaping the active-site pocket for better substrate recognition and optimizing the preorganization and reactivity of the catalytic base.

To analyse the stability of the substrate within the active site, we conducted microsecond MD simulations of Des27 and Des27.7, starting

![](images/9629dda60dc218f9baa17bffe05d8d6558e5cfcb06e8509cb3dcfbe515ea97a5.jpg)

![](images/f97a3a2e7201a5d31899e81fa56585f686791bfc46d5e33cd5c582124dd12c6c.jpg)

![](images/87ba402fa401b77021501bdaaa25aa50c1e19d7d4c2e6876106b43807cbfd2cc.jpg)

![](images/1a16f0b6bd12e1d57d511ee77894691e64acd8cec1c938cf9778fa5a2ae1f42f.jpg)  
competent conformations: one in which the nitro group is buried inside the TIM barrel (in, blue) and another in which it is solvent exposed (out, orange). Shown are two representative conformations from the MD simulations. e, Activation free energy for the proton abstraction of 5-nitrobenzisoxazole, comparing  $\Delta G^{\ddagger}$  computed from the experimentally determined  $k_{\mathrm{cat}}$  values (mean  $\pm$  s.d. of 2 and 5 biological replicates for Des27 and Des27.7, respectively) using the Eyring rate equation, assuming  $T = 298\mathrm{K}$  (experiment), and the corresponding values calculated for 'in' and 'out' substrate conformations (mean  $\pm$  s.d. over 30 independent EVB trajectories per system). A two-sample Wilcoxon rank-sum test (two-sided) indicated statistically significant differences in the calculated activation free energies between the 'in' and 'out' conformations for Des27.7 ( $P = 7.7\times 10^{-9}$ ) but not for Des27 ( $P = 0.088$ ). R.e.u., Rosetta energy units.

from their ligand-bound design models. In both cases and across all replicas, the substrate exited and re-entered the active-site pocket multiple times (Extended Data Fig. 5), with Des27.7 showing five times more substrate retention (Fig. 3c and Supplementary Table 2). This contrasts with the typical scenario in MD simulations in which unbinding events are terminal $^{49,50}$ . Thus, the MD simulations indicate that our designs exhibit high affinity for the substrate, and that Des27.7 improves it further. We also noticed that the substrate may enter the pocket in two reactive conformations that are inverted: one that closely matches the design model, with the nitro substituent occupying the entrance to the active site, and one in which it is inverted by approximately  $180^{\circ}$  (Fig. 3d). Empirical valence bond (EVB) calculations of reaction free energies $^{51}$  show similar energy profiles for both conformations, indicating that both are catalytically competent (Fig. 3e and Supplementary Table 3). Taken together, the MD and EVB calculations suggest that the experimentally measured results reflect the sum of both reaction modes, with the 'out' conformation (Fig. 3c) being occupied a greater fraction of MD simulation time than the 'in' conformation, but with EVB

![](images/ac8f23db51e4d39fb421235a695c44f847762b6893868baffdcf6ada1f6d4aa9.jpg)  
Fig. 4 | Deconvoluting the contributions of the mutations in Des27.7 reveals necessary and sufficient components for effective de novo enzyme design. Apparent melting temperature and catalytic efficiency of Des27.7 (top row) are compared with variants in which design components are ablated (X symbols).  
The number of mutations relative to the modular assembly baseline is indicated in parentheses. Data represent the mean  $\pm$  s.d. of 2-5 biological replicates. Muts, number of mutations; ND, not detected.

predicting the in conformation as being slightly more reactive in the optimized Des27.7 variant (Fig. 3e). Further, although such desolvated nitro group ('in') conformations were observed in previous de novo designed Kemp eliminases $^{6,49,50}$ , in those studies only one conformation was catalytically competent $^{50}$ . Thus, the high efficiency of Des27.7 may be partly due to the high preorganization of the active-site pocket and its ability to accommodate productive substrate interactions through distinct conformations.

To verify the molecular accuracy of the design process, we determined the structure of Des27.7 in the unbound form by crystallographic analysis (Extended Data Table 2; PDB 9HVB). All active-site positions aligned well with the design conception (less than  $0.7\AA$  all-atom root mean squared deviation (r.m.s.d.) across 20 residues), including the catalytic Asp162, although a slight shift (r.m.s.d.  $0.78\AA$ ) was observed in the orientation of Phe113. Outside the active-site pocket, 180 of 257 positions aligned with backbone r.m.s.d.  $< 0.6\AA$ , but 65 amino acids either deviated or did not exhibit significant electron density, probably due to backbone flexibility in this region (Extended Data Fig. 6a,b). This fragment is known to be dynamic in the IGPS protein family[52], but it lies outside the active-site pocket and probably does not contribute directly to reactivity and substrate recognition. Taken together, our results verify a fully computational pipeline that designs an accurate de novo active site and generates a stable and high-efficiency new-to-nature enzyme.

# Necessary and sufficient conditions for design

Our computational workflow is based on the combination of several design components, each of which introduces multiple mutations that address aspects that are critical for efficient biocatalysis, such as backbone diversity, stability, foldability and activity. We next probed whether each of these components contributes to the intended property and whether all are essential.

We started by examining whether modular assembly and design is essential for generating diverse backbones. Instead of applying modular assembly and design, we applied the subsequent steps of the workflow to 1,072 representative IGPSs that were modelled using AlphaFold2 (Methods). We tested 55 designs (design round 2), of which 49 were solubly expressed (89%) and 28 (50%) exhibited apparent cooperative unfolding with apparent melting temperature ( $T_{\mathrm{m}}$ ) values  $47 - 88^{\circ}\mathrm{C}$ . In total, 70% of the cooperatively folded designs

(20 designs) showed measurable KE activity with  $k_{\mathrm{cat}} / K_{\mathrm{M}}$  in the range of  $0.5 - 155\mathrm{M}^{-1}\mathrm{s}^{-1}$ , demonstrating that the workflow can design stable and functional Kemp eliminations in a wide range of different starting points. As expected, designs that did not show cooperative unfolding lacked KE activity. We applied FuncLib to the active sites of six designs and tested 9-14 variants for each starting point. In five cases, catalytic efficiencies improved by 3-10-fold (Supplementary Table 1), with the highest catalytic efficiency reaching  $300\mathrm{M}^{-1}\mathrm{s}^{-1}$  (R2.Des39.2). We determined the crystallographic structure of two designs, R2.Des39 ( $k_{\mathrm{cat}} / K_{\mathrm{M}}100\mathrm{M}^{-1}\mathrm{s}^{-1}$ ) and Des49 ( $k_{\mathrm{cat}} / K_{\mathrm{M}}150\mathrm{M}^{-1}\mathrm{s}^{-1}$ ) (Extended Data Fig. 6c-i, PDB IDs 9HVH and 9HVG and Extended Data Table 2). The active sites were close to their design conceptions (r.m.s.d.  $< 0.6\AA$  and r.m.s.d.  $< 0.82\AA$ , respectively), but, in both cases, several loops either lacked electron density or exhibited significant conformational changes compared with the designs, which could impede substrate entry to the active site[53]. To explore whether the foldability of these loops could be improved, we applied FuncLib to stabilize these regions according to the design models. Three of 16 FuncLib variants of Des39.2 showed a significant increase in catalytic efficiency, with improvements up to 20-fold compared with the original design, reaching  $k_{\mathrm{cat}} / K_{\mathrm{M}}2,000\mathrm{M}^{-1}\mathrm{s}^{-1}$  (Extended Data Table 1 and Supplementary Table 1), but none surpassed the performance of Des27.7. These results demonstrate that large-scale artificial intelligence-based structure prediction of natural enzymes provides a valuable resource for de novo enzyme design, and that the computational workflow reproductively generates efficient enzymes. In this case, however, optimization with FuncLib reached superior catalytic parameters in the designs derived from modular assembly, which may reflect the greater structural diversity in these designs.

As a next step to understanding the necessary and sufficient conditions for design of high-efficiency enzymes, we deconvoluted the contributions of each design component to the high stability and activity of Des27.7. As a baseline, we tested the outcome of combinatorial assembly and design alone (with 92 mutations relative to any natural protein), excluding both the PROSS-based stability mutations and the active-site design. This variant exhibited an apparent melting temperature of  $57^{\circ}\mathrm{C}$  and no detectable KE activity. Adding the 11 PROSS-designed mutations substantially improved both bacterial expression and thermal stability  $(69^{\circ}\mathrm{C})$  (Fig. 4 and Supplementary Fig. 1). Separately, grafting the active site from Des27.7 (15 mutations) onto the combinatorial assembly starting point (without PROSS stabilizing mutations) conferred high activity levels  $(2,900\mathrm{M}^{-1}\mathrm{s}^{-1})$  but fourfold lower than in

# Article

Des27.7. Combining the modular assembly, PROSS and the designed active site yielded a synergistic, higher-than-expected improvement in both stability and reactivity beyond the contribution of the individual components. Thus, despite the large number of mutations introduced by each computational component, resulting designs did not exhibit the trade-offs between stability and activity that were often reported in laboratory-evolution campaigns $^{7,21,54}$ . Furthermore, although active-site mutations are often assumed to compromise stability $^{21}$ , in our case, the designed active site contributed positively to stability. Collectively, these findings emphasize the importance of stabilizing the entire protein to obtain efficient enzymes and the potential for synergy between stability and activity-promoting mutations when using reliable sequence design methods $^{21}$ .

Finally, we evaluated the contribution of the theozyme to the activity of Des27.7. Mutating the catalytic base Asp162 to Ala completely abolished activity, verifying that the designed base is essential. Remarkably, this single-point mutation also markedly increased protein stability, with the apparent melting temperature rising from  $85^{\circ}\mathrm{C}$  in Des27.7 to above boiling point (Fig. 4). This significant increase in stability underscores the strong destabilization induced by desolvating a charged group in the core of the active site and the importance of effective stability design methods.

We then tested whether the second theozyme residue, Phe113, was essential by replacing it with point mutations suggested by atomistic design. Replacement with Met and Leu exhibited similar Rosetta energies to the original Phe, and we subjected these point mutants to experimental analysis. The Met mutation showed similar catalytic parameters to Phe (Extended Data Table 1), suggesting that an aromatic identity is not essential at this position. Strikingly, Phe113Leu led to an order of magnitude increase in catalytic efficiency and rate to  $k_{\mathrm{cat}} / K_{\mathrm{M}}$  of  $123,000\mathrm{M}^{-1}\mathrm{s}^{-1}$  and  $k_{\mathrm{cat}}$  of  $30\mathrm{s}^{-1}$ , surpassing by two orders of magnitude recently designed enzymes in artificial intelligence-generated proteins  $(k_{\mathrm{cat}} = 0.03 - 0.7\mathrm{s}^{-1})^{14,15,35}$ . To understand the reasons for this large gain in efficiency, we compared Leu113 in models of the unbound and transition states. Unlike the reorientation observed for Phe113 between the ligand-bound model and unbound experimental structure of Des27.7 (Extended Data Fig. 7a), Leu113 exhibits almost no sidechain conformation changes (Extended Data Fig. 7b), suggesting that this mutation improves active-site preorganization.

We note that the aromatic theozyme residue was forced in all our design steps and was based on previous Kemp eliminase design studies<sup>1,3</sup>. The fact that a completely aliphatic active-site pocket effectively accelerates the KE reaction is in line with the observation that London dispersion forces are sufficient for transition-state stabilization<sup>55</sup>. This finding challenges a two-decade assumption in computational Kemp eliminase design that an aromatic residue is important for ligand binding<sup>1,3</sup>, demonstrating how de novo design of function can expose shortcomings in our understanding of fundamental aspects in biocatalysis.

# Conclusions

De novo enzyme design has until now resulted in rudimentary catalytic rates and required iterative random mutagenesis to close the gap with enzymes found in nature. Our strategy uses recent approaches for reliable backbone and sequence design in natural folds to generate diverse TIM-barrel backbones, stabilize the protein and design preorganized active-site constellations. This comprehensive design approach allowed us to explore the principles underlying high stability and activity in KE biocatalysis. In a single step, we generated a dozen designs with activities that spanned three orders of magnitude and gained insights into the determinants of high-efficiency catalysis. The best variant showed high stability and remarkable catalytic efficiency for a fully designed enzyme (greater than  $85^{\circ}\mathrm{C}$  and  $12,700\mathrm{M}^{-1}\mathrm{s}^{-1}$ , respectively), which was increased to over  $10^{5}\mathrm{M}^{-1}\mathrm{s}^{-1}$  with a single designed mutation. Active-site preorganization combined with the ability to

adopt multiple catalytically competent substrate-bound modes distinguishes this design from previously generated ones. Importantly, our best design exhibited a catalytic rate  $(30\mathrm{s}^{-1})$  and efficiency on par with the median values of natural enzymes<sup>16</sup>. Thus, the ability to design large sets of diverse backbones and encode high protein stability and active-site preorganization is necessary and sufficient for generating high-efficiency enzymes of model reactions. Furthermore, contrary to recent suggestions<sup>11</sup>, the results confirm that current atomistic methods are already sufficiently reliable to generate efficient enzymes in natural folds without extensive experimental screening, big-data analyses or artificial intelligence-generated scaffolds. Future improvements in modelling theozymes may enable fully programmable biocatalysis.

# Online content

Any methods, additional references, Nature Portfolio reporting summaries, source data, extended data, supplementary information, acknowledgements, peer review information; details of author contributions and competing interests; and statements of data and code availability are available at https://doi.org/10.1038/s41586-025-09136-2.

1. Röthlisberger, D. et al. Kemp elimination catalysts by computational enzyme design. Nature 453, 190-195 (2008).  
2. Siegel, J. B. et al. Computational design of an enzyme catalyst for a stereoselective bimolecular Diels-Alder reaction. Science 329, 309-313 (2010).  
3. Privett, H. K. et al. Iterative approach to computational enzyme design. Proc. Natl Acad. Sci. USA 109, 3790-3795 (2012).  
4. Jiang, L. et al. De novo computational design of retro-aldol enzymes. Science 319, 1387-1391 (2008).  
5. Yeh, A. H.-W. et al. De novo design of luciferases using deep learning. Nature 614, 774-780 (2023).  
6. Blomberg, R. et al. Precision is essential for efficient catalysis in an evolved Kemp eliminase. Nature 503, 418-421 (2013).  
7. Khersonsky, O. et al. Bridging the gaps in design methodologies by evolutionary optimization of the stability and proficiency of designed Kemp eliminase KE59. Proc. Natl Acad. Sci. USA 109, 10358-10363 (2012).  
8. Giger, L. et al. Evolution of a designed retro-aldolase leads to complete active site remodeling. Nat. Chem. Biol. 9, 494-498 (2013).  
9. Patsch, D. et al. Enriching productive mutational paths accelerates enzyme evolution. Nat. Chem. Biol. 20, 1662-1669 (2024).  
10. Korendovych, I. V. & DeGrado, W. F. Catalytic efficiency of designed catalytic proteins. Curr. Opin. Struct. Biol. 27, 113-121 (2014).  
11. Lovelock, S. L. et al. The road to fully programmable protein catalysis. Nature 606, 49-58 (2022).  
12. Listov, D., Goverde, C. A., Correia, B. E. & Fleishman, S. J. Opportunities and challenges in design and optimization of protein function. Nat. Rev. Mol. Cell Biol. 25, 639-653 (2024).  
13. Marques, S. M., Planas-Iglesias, J. & Damborsky, J. Web-based tools for computational enzyme design. Curr. Opin. Struct. Biol. 69, 19-34 (2021).  
14. Braun, M. et al. Computational design of highly active de novo enzymes. Preprint at bioRxiv https://doi.org/10.1101/2024.08.02.606416 (2024).  
15. Lauko, A. et al. Computational design of serine hydrolases. Science https://doi.org/10.1126/science.adu2454 (2025).  
16. Bar-Even, A. et al. The moderately efficient enzyme: evolutionary and physicochemical trends shaping enzyme parameters. Biochemistry 50, 4402-4410 (2011).  
17. Khare, S. D. & Fleishman, S. J. Emerging themes in the computational design of novel enzymes and protein-protein interfaces. FEBS Lett. 587, 1147-1154 (2013).  
18. Baker, D. An exciting but challenging road ahead for computational enzyme design. Protein Sci. 19, 1817-1819 (2010).  
19. Kries, H., Blomberg, R. & Hilvert, D. De novo enzymes by computational design. Curr. Opin. Chem. Biol. 17, 221-228 (2013).  
20. Kiss, G., Celebi-Olçüm, N., Moretti, R., Baker, D. & Houk, K. N. Computational enzyme design. Angew. Chem. Int. Ed. Engl. 52, 5700-5725 (2013).  
21. Goldenzweig, A. & Fleishman, S. J. Principles of protein stability and their application in computational design. Annu. Rev. Biochem. 87, 105-129 (2018).  
22. Frushicheva, M. P., Cao, J., Chu, Z. T. & Warshel, A. Exploring challenges in rational enzyme design by simulating the catalysis in artificial Kemp eliminase. Proc. Natl Acad. Sci. USA 107, 16869-16874 (2010).  
23. Otten, R. et al. How directed evolution reshapes the energy landscape in an enzyme to boost catalysis. Science 370, 1442-1446 (2020).  
24. Nagel, Z. D. & Klinman, J. P. A 21st century revisionist's view at a turning point in enzymology. Nat. Chem. Biol. 5, 543-550 (2009).  
25. Vaisnier Welborn, V. & Head-Gordon, T. Computational design of synthetic enzymes. Chem. Rev. 119, 6613-6630 (2019).  
26. Chu, A. E., Lu, T. & Huang, P.-S. Sparks of function by de novo protein design. Nat. Biotechnol. 42, 203-215 (2024).  
27. Lipsh-Sokolik, R. et al. Combinatorial assembly and design of enzymes. Science 379, 195-201 (2023).  
28. Khersonsky, O. et al. Automated design of efficient and functionally diverse enzyme repertoires. Mol. Cell 72, 178-186.e5 (2018).

29. Goldenzweig, A. et al. Automated structure- and sequence-based design of proteins for high bacterial expression and stability. Mol. Cell 63, 337-346 (2016).  
30. Rocklin, G. J. et al. Global analysis of protein folding using massively parallel design, synthesis, and testing. Science 357, 168-175 (2017).  
31. Polizzi, N. F. & DeGrado, W. F. A defined structural unit enables de novo design of small-molecule-binding proteins. Science 369, 1227-1233 (2020).  
32. Watson, J. L. et al. De novo design of protein structure and function with RFdiffusion. Nature 620, 1089-1100 (2023).  
33. Frank, C. et al. Scalable protein design using optimization in a relaxed sequence space. Science 386, 439-445 (2024).  
34. Lu, T., Liu, M. H., Chen, Y., Kim, J. & Huang, P.-S. Assessing generative model coverage of protein structures with SHAPES. Preprint at bioRxiv https://doi.org/10.1101/2025.01.09.632260 (2025).  
35. Kim, D. et al. Computational design of metallohydrolases. Preprint at bioRxiv https://doi.org/10.1101/2024.11.13.623507 (2024).  
36. Copeland, R. A. Enzymes: A Practical Introduction to Structure, Mechanism, and Data Analysis (Wiley-VCH, 1996).  
37. Sillitoe, I. et al. CATH: expanding the horizons of structure-based functional annotations for genome sequences. Nucleic Acids Res. 47, D280-D284 (2019).  
38. Nagano, N., Orengo, C. A. & Thornton, J. M. One fold with many functions: the evolutionary relationships between TIM barrel families based on their sequences, structures and functions. J. Mol. Biol. 321, 741-765 (2002).  
39. Huang, P. S. et al. De novo design of a four-fold symmetric TIM-barrel protein with atomic-level accuracy. Nat. Chem. Biol. 12, 29-34 (2016).  
40. Eisenbeis, S. et al. Potential of fragment recombination for rational design of proteins. J. Am. Chem. Soc. 134, 4019-4022 (2012).  
41. Lapidoth, G. et al. Highly active enzymes by automated combinatorial backbone assembly and sequence design. Nat. Commun. 9, 2780 (2018).  
42. Lipsh-Sokolik, R., Listov, D. & Fleishman, S. J. The AbDesign computational pipeline for modular backbone assembly and design of binders and enzymes. Protein Sci. 1, 151-159 (2021).  
43. Zanghellini, A. et al. New algorithms and an in silico benchmark for computational enzyme design. Protein Sci. 15, 2785-2794 (2006).  
44. Leaver-Fay, A. et al. ROSETTA3: an object-oriented software suite for the simulation and design of macromolecules. Methods Enzymol. 487, 545-574 (2011).  
45. Warszawski, S., Netzer, R., Tawfik, D. S. & Fleishman, S. J. A 'fuzzy' logic language for encoding multiple physical traits in biomolecules. J. Mol. Biol. 426, 4125-4138 (2014).  
46. Listov, D. et al. Assessing and enhancing foldability in designed proteins. Protein Sci. 31, e4400 (2022).

47. Na, J., Houk, K. N. & Hilvert, D. Transition state of the base-promoted ring-opening of isoxazoles. Theoretical prediction of catalytic functionalities and design of haptens for antibody production. J. Am. Chem. Soc. 118, 6462-6471 (1996).  
48. Tantillo, D. J., Chen, J. & Houk, K. N. Theozymes and compuzymes: theoretical models for biological catalysis. Curr. Opin. Chem. Biol. 2, 743-750 (1998).  
49. Hong, N. S. et al. The evolution of multiple active site configurations in a designed enzyme. Nat. Commun. 9, 3900 (2018).  
50. Gutierrez-Rus, L. I. et al. Enzyme enhancement through computational stability design targeting NMR-determined catalytic hotspots. J. Am. Chem. Soc. https://doi.org/10.1021/jacs.4c09428 (2025).  
51. Warshel, A. & Weiss, R. M. An empirical valence bond approach for comparing reactions in solutions and in enzymes. J. Am. Chem. Soc. 102, 6218-6226 (1980).  
52. Hupfeld, E. et al. Conformational modulation of a mobile loop controls catalysis in the  $(\beta \alpha)8$ -barrel enzyme of histidine biosynthesis HisF. JACS Au 4, 3258-3276 (2024).  
53. Schlee, S. et al. Relationship of catalysis and active site loop dynamics in the  $(\beta \alpha)8$ -barrel enzyme indole-3-glycerol phosphate synthase. Biochemistry 57, 3265-3277 (2018).  
54. Goldsmith, M. et al. Overcoming an optimization plateau in the directed evolution of highly efficient nerve agent bioscavengers. Protein Eng. Des. Sel. 30, 333-345 (2017).  
55. Kemp, D. S., Cox, D. D. & Paul, K. G. Physical organic chemistry of benzisoxazoles. IV. Origins and catalytic nature of the solvent rate acceleration for the decarboxylation of 3-carboxybenzisoxazoles. J. Am. Chem. Soc. 97, 7312-7318 (1975).

Publisher's note Springer Nature remains neutral with regard to jurisdictional claims in published maps and institutional affiliations.

![](images/4ce4224abae3b5090eaa6aa3a6971493727ac710dcecbeb20278e79d62fff1b8.jpg)

Open Access This article is licensed under a Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License, which permits any non-commercial use, sharing, distribution and reproduction in any medium or

format, as long as you give appropriate credit to the original author(s) and the source, provide a link to the Creative Commons licence, and indicate if you modified the licensed material. You do not have permission under this licence to share adapted material derived from this article or parts of it. The images or other third party material in this article are included in the article's Creative Commons licence, unless indicated otherwise in a credit line to the material. If material is not included in the article's Creative Commons licence and your intended use is not permitted by statutory regulation or exceeds the permitted use, you will need to obtain permission directly from the copyright holder. To view a copy of this licence, visit http://creativecommons.org/licenses/by-nc-nd/4.0/.

© The Author(s) 2025

# Article

# Methods

# Backbone generation and stabilization

Modular assembly and design was applied as described in ref. 42. In brief, five different IGPS structures (PDB entries 1LBF, 1I4A, 1JCM, 1VC4 and 4FB7) were aligned and segmented into five fragments according to points of maximum structure conservation at positions 44, 105, 154 and 206 (numbering relative to PDB entry 1I4N). The fragments were then computationally combined all against all, and Rosetta sequence design was applied to optimize the stability and compatibility between the segments, resulting in 2,500 backbones. Design calculations were constrained using a position-specific scoring matrix (PSSM) that was generated for each structure using PROSS $^{29}$ . For designs 37-73, a further stabilization protocol was applied. This protocol, based on mutational scanning with PSSM constraints, identifies the most beneficial mutations across the protein. These mutations are combined and threaded onto the input structure. These backbones were then evaluated by an activity predictor $^{27}$  and the top 1,000 designs were chosen.

To implement the workflow without recourse to modular assembly and design (design round 2), we used BLAST to search the nonredundant sequence database with the sequence of the Thermotoga maritima IGPS (PDB entry 114N), identifying 4,381 IGPS homologues. These were clustered with CD-HIT $^{56}$  by  $30 - 90\%$  sequence identity to one another and 1,200 were selected for further analysis. The structures of these sequences were modelled using ColabFold AlphaFold2 (refs. 57,58). Models with average local confidence in predicted structures (predicted local distance difference test (pLDDT)) scores below 90 were discarded, leaving 1,072 backbones. All structures were subjected to PROSS stability design calculations $^{29}$  and Design 8 for each was selected for further calculations. For models generated using AlphaFold2, PROSS design was disabled in amino acids that exhibited low predicted confidence  $(\mathrm{pLDDT} < 90\%)$  and those that were  $5\AA$  from these residues $^{59}$ .

# Catalytic site generation

Theozyme geometries (Supplementary Table 4) were based on previous calculations<sup>1</sup>. Geometric parameters that define the catalytic placements, such as tolerance, penalty coefficient, periodicity and number of matching samples to test, were manually adjusted<sup>60</sup>. The interaction between the catalytic base and the acidic carbon on the ligand was defined as covalent to mimic transition-state geometry. Theozyme placement was carried out using the Rosetta Matcher algorithm<sup>43</sup>. All positions inside or in the opening of the active site were allowed for theozyme matching (Fig. 1, step 3).

# Initial active-site design and filtering

After matching, Rosetta sequence design was performed in an 8 Å shell around the ligand and catalytic residues. The design was performed under the enzyme and PSSM constraints. To constrain the sequence space, the catalytic residues of the IGPS family, as described by the M-CSA database<sup>61</sup>, underwent Rosetta computational mutation scanning, and all mutations with  $\Delta \Delta G_{\mathrm{system}} < +1$  R.e.u. compared with the starting identity were included as allowed for design. The Rosetta Match and design steps generated  $10^{5}$  to  $10^{6}$  designs for each starting structure. Designs were filtered on the basis of a 'fuzzy'-logic objective function<sup>45</sup> that balanced potentially conflicting criteria: energy density (system energy divided by the protein length), energy rank relative to other designs in the same backbone, active-site vdW energy, catalytic base vdW, ligand solvation and accuracy of the enzyme geometry. vdW energy is defined as the sum of the Rosetta atomistic energy terms fa_a tr and fa_rep (as weighted in Rosetta scoring function<sup>62</sup>).

# Active-site and core stabilization

To enhance active-site stability, we performed an enumeration of all low-energy mutations in the active site with  $\Delta \Delta G_{\mathrm{system}} < +3$  R.e.u.

and chose the top variant. To ensure amino acid optimality throughout the protein, a pSUFER $^{46}$  scan was performed on the whole protein excluding the active site. Flagged positions, those with at least five favourable amino acid substitutions  $(\Delta \Delta G_{\mathrm{system}} < 0)$ , were redesigned using FuncLib calculations $^{28}$ . The lowest-energy design was selected.

# Computational validation

Active-site preorganization was analysed by performing extensive rigid-body minimization in the absence of the ligand. Structures in which the catalytic base exhibited an r.m.s.d.  $>1.2\AA$  relative to the ligand-unbound model were discarded. For the R2 series the workflow included an extra validation step comparing the bound model and the AlphaFold2-predicted model. Designs were accepted if the r.m.s.d. between the AlphaFold2 model and the Rosetta model was less than 1 Å.

# Active-site optimization

All functional variants identified through experimental screening were optimized by identifying diverse and stable active-site constellations using FuncLib $^{28}$ . FuncLib uses two filters to constrain the enumerated sequence space: a filter based on homologous sequences and exclusion of destabilizing point mutations. However, in de novo design of function, the homologous sequence filter is irrelevant and was omitted. For experimental screening, the 10-15 lowest-energy designs were selected.

# Protein expression

The designed genes were ordered from Twist Bioscience, cloned into pET28 plasmid with an N-terminal His-tag, followed by a bdSUMO tag. Plasmids were transformed into Escherichia coli BL21 (DE3) cells. For expression,  $50\mathrm{ml}$  of 2YT medium supplemented with  $50~\mu \mathrm{g}~\mathrm{ml}^{-1}$  kanamycin was inoculated with  $500~\mu \mathrm{l}$  of overnight culture produced from a single colony and grown at  $37^{\circ}\mathrm{C}$  until optical density  $(\mathrm{OD})_{600}$  0.6-0.8. Overexpression was induced by adding  $1\mathrm{mM}$  IPTG and the cultures were grown for  $20\mathrm{h}$  at  $16^{\circ}\mathrm{C}$  and collected, and the pellet was frozen at  $-20^{\circ}\mathrm{C}$ . The cells were resuspended in basic buffer ( $50\mathrm{mM}$  Tris-Cl pH 7.25,  $200\mathrm{mMNaCl}$ ) supplemented with  $10~\mu \mathrm{g}~\mathrm{ml}^{-1}$  lysozyme, protease-inhibitor cocktail (Sigma) and benzonase, lysed by sonication and centrifuged at  $20,000g$  for  $30\mathrm{min}$  at  $4^{\circ}\mathrm{C}$ . The soluble fraction was loaded onto an Ni-NTA (nitrilotriacetic acid) column and washed twice with basic buffer and  $20\mathrm{mM}$  imidazole. The protein was subjected to overnight on-column Sumo protease cleavage at  $4^{\circ}\mathrm{C}$  ( $5\mu \mathrm{g}~\mathrm{ml}^{-1}$  in basic buffer). Protein purity was assessed by SDS-PAGE. Protein concentration was determined using Pierce BCA protein assay kit. For crystallography, large-scale expression was performed in  $1,500\mathrm{ml}$  of culture. After Ni-NTA purification and bdSUMO cleavage, the protein was purified by gel filtration (HiLoad 26/600 Superdex75 preparative grade column, GE).

# Activity assay and determination of kinetic parameters

Product formation was monitored spectrophotometrically at  $380\mathrm{nm}$  in  $200 - \mu l$  reaction volumes using 96-well plates. For initial screening, the reactions were started by adding  $150~\mu l$  of  $1\mathrm{mM}$  5-nitrobenzisoxazole in basic buffer to  $50~\mu l$  of purified protein. 5-Nitrobenzisoxazole was used from  $0.1\mathrm{M}$  stock in acetonitrile. For the kinetic characterization,  $150~\mu l$  of 5-nitrobenzisoxazole at various concentrations (final  $0.05 - 0.75\mathrm{mM}$  in basic buffer with  $1\mathrm{mM}$  acetonitrile) was mixed with  $50~\mu l$  of purified protein. Kinetic parameters were obtained by fitting the data to the Michaelis-Menten equation  $\upsilon_{0} = k_{\mathrm{cat}}[\mathrm{E}]_{0}[\mathrm{S}]_{0}/$ $([\mathrm{S}]_{0} + K_{\mathrm{M}})$ . At low substrate concentrations the data were fitted to the linear regime of the Michaelis-Menten model  $\upsilon_{0} = [\mathrm{S}]_{0}[\mathrm{E}]_{0}k_{\mathrm{cat}} / K_{\mathrm{M}}$  and  $k_{\mathrm{cat}} / K_{\mathrm{M}}$  values were inferred from the slope. All measurements in the main text were performed in biological duplicates or triplicates.

# Thermal stability

Apparent  $T_{\mathrm{m}}$  measurements were performed using nanoscale differential scanning fluorimetry (nanoDSF) experiments (Prometheus NT.Plex instrument, NanoTemper Technologies). The temperature ramp was  $20 - 95^{\circ}\mathrm{C}$  with  $1.0^{\circ}\mathrm{C}\min^{-1}$  slope.

# Crystallization, data collection and structure determination

Crystals were grown at  $19^{\circ}\mathrm{C}$  using the sitting-drop vapour diffusion method. Diffraction data were collected from a single crystal flash-cooled to  $100\mathrm{K}$ , using a wavelength of  $1.34\AA$ . Data were collected using an in-house Rigaku liquid-metal-jet X-ray Synergy System with a HyPix Arc  $150^{\circ}$  detector. AlphaFold2 (ref. 57) was used to generate all three models for molecular replacement (Extended Data Table 2). Initial models were iteratively rebuilt and refined using COOT $^{63}$  and PHENIX $^{64}$ . Model geometry was evaluated using MOLPROBIT $^{65}$ . Atomic coordinates and structure factors for Des27.7, R2.Des39 and R2.Des49 are deposited in the PDB database under accession numbers 9HVB, 9HVH and 9HVG, respectively.

# Specific crystallization conditions

Des27.7: the well solution contained  $0.15\mathrm{M}$  lithium sulfate monohydrate,  $0.1\mathrm{M}$  citric acid  $(\mathsf{pH}3.5)$  and  $18\%$  polyethylene glycol (PEG) 6000. Diffraction data were collected to  $2.0\AA$ . Des27.7 crystallized in the  $\mathsf{P6}_1$  space group, with one subunit in the asymmetric unit.

R2.Des39: the well solution contained 0.07 M citric acid, 0.03 M Bis-Tris propane (pH 3.4) and  $14\%$  PEG 3350. Diffraction data were collected to 2.1 Å resolution. R2.Des39 crystallized in the  $\mathrm{P2}_{1}$  space group, with two subunits in the asymmetric unit.  
R2.Des49: the well solution contained  $8\%$  Tacsimate  $(\mathrm{pH}7.0)$  and  $20\%$  PEG 3350. Diffraction data were collected to  $1.9\mathring{\mathrm{A}}$  resolution. R2.Des49 crystallized in the  $\mathrm{C222}_{1}$  space group, with one subunit in the asymmetric unit.

# MD and EVB simulations

System setup. Two designed Kemp eliminases, Des27 and Des27.7, were simulated in both their ligand-bound and unbound forms, using MD simulations to model dynamics, and EVB simulations $^{51}$ . All simulations were initiated from the FuncLib design models for each variant. Ligand-bound simulations were performed in complex with the substrate 5-nitrobenzisoxazole. The partial charges for the substrate were calculated using restrained electrostatic potential $^{66}$  fitting at the HF/6-31 G(d) level of theory with Antechamber $^{67}$ , on the basis of gas-phase geometries optimized at the B3LYP/6-31 G(d) level of theory in Gaussian 16 Rev. B.01 (ref. 68). All other force field parameters for the substrate were obtained from the General AMBER Force Field (GAFF2) $^{69}$ . Residue protonation states were checked using PROPKA 3.0 (refs. 70,71) to estimate sidechain  $\mathsf{pK}_{\mathrm{a}}\mathsf{s}$ , coupled with visual examination using PyMOL, on the basis of which all residues were kept in their standard protonation states at physiological pH. For simulations of the unbound system, the catalytic residue Asp162 was modelled in its protonated form. All systems were solvated in a truncated octahedral water box containing OPC water molecules $^{72}$ , extending  $11.0\AA$  from the protein in all directions. Neutralization was achieved using  $12\mathrm{Mg}^{2+}$  and  $12\mathrm{Cl}^-$  counterions for the three variants. Protonation patterns of histidine residues for each system are collected in Supplementary Table 5. Non-standard substrate parameters are provided in Supplementary Table 6 and in the Zenodo data package available at https://doi.org/10.5281/zenodo.14563437 (ref. 73).

Classical MD simulations. All MD simulations in this work were performed using the HIP-accelerated version of Amber24 (ref. 74) using the ff19SB force field $^{75}$  and the OPC water model $^{72}$ . MD simulations for all systems followed the same protocol, used also in previous work

modelling designed Kemp eliminases $^{50}$ . For a detailed description, see ref. 50. In brief, each trajectory was first energy minimized with 100 steps of the steepest-descent algorithm, followed by 900 steps of conjugate gradient minimization, applying a 100-kcal  $\mathrm{mol}^{-1}\mathring{\mathrm{A}}^{-2}$  restraint to all solute (protein and substrate) atoms. The system was then heated from 50 to  $300\mathrm{K}$  in an NVT ensemble using simulated annealing, reaching  $300\mathrm{K}$  within the first 100 ps and continuing for a total of 1 ns with a 1-fs time step. Langevin temperature control $^{76}$  was used with a collision frequency of  $1\mathrm{ps}^{-1}$ . During this stage, the 100-kcal  $\mathrm{mol}^{-1}\mathring{\mathrm{A}}^{-2}$  solute restraints were maintained and subsequently reduced to 10 kcal  $\mathrm{mol}^{-1}\mathring{\mathrm{A}}^{-2}$  in later equilibration steps. A second energy minimization and heating step followed, with positional restraints applied to solute heavy atoms. During subsequent equilibration, the restraints were progressively reduced from 10 to 1 to 0.1 kcal  $\mathrm{mol}^{-1}\mathring{\mathrm{A}}^{-2}$  before being fully removed. The systems, now with no restraints applied, underwent final equilibration for 1 ns in an NPT ensemble (300 K, 1 atm) using a Berendsen barostat $^{77}$  with a 1-ps pressure relaxation time and Langevin temperature control (collision frequency of  $1\mathrm{ps}^{-1}$ ). The SHAKE algorithm $^{78}$  was applied to constrain all bonds involving hydrogen atoms, and all equilibration simulations used a 1-fs time step. Production MD runs were performed using a 4-fs time step, enabled by hydrogen mass repartitioning $^{79}$  and the SHAKE algorithm $^{78}$ , with an 8 Å direct space non-bonded cutoff, Langevin temperature control (collision frequency of  $1\mathrm{ps}^{-1}$ ) and a Berendsen barostat (pressure relaxation time of 1 ps). Equilibration of these trajectories is shown in Extended Data Fig. 4d,e. The final production trajectories were 1-μs long for each system, with 5 independent replicas per system, resulting in a total of 5 μs of simulation time per system and 15 μs across all systems.

EVB simulations. EVB simulations were performed on the Des27 and Des27.7 variants, using both substrate conformers ('in' and 'out'; Fig. 3c) observed as being dominant in the MD simulations, and following the same protocol described in detail in ref. 50. Reactive in and out conformers were extracted from our MD simulations and overlaid onto the FuncLib predicted structures of Des27 and Des27.7 as starting coordinates for the EVB simulations. Before the EVB simulations, in all cases, the enzyme-substrate complex was minimized with Amber24 (ref. 74) in vacuum, with 2,500 steps of the steepest-descent algorithm, followed by 2,500 steps of conjugate gradient minimization, applying 10-kcal  $\mathrm{mol}^{-1}\mathring{\mathrm{A}}^{-2}$  positional restraints on all heavy (non-hydrogen) atoms. The minimization was repeated with the same steps, with 5-kcal  $\mathrm{mol}^{-1}\mathring{\mathrm{A}}^{-2}$  positional restraint on protein  $C_{\alpha}$ -atoms, and substrate heavy atoms, and with twice as many steps, keeping the restraint only on the substrate heavy atoms.

All EVB simulations were performed using the Q6 simulation package $^{80}$ , the OPLS-AA force field $^{81}$ , the TIP3P water model $^{82}$  and the surface constrained all atom solvent (SCAAS) model $^{83}$  to describe solvent. Long-range interactions were described using the local reaction field approach $^{84}$ . Protonation states of ionizable residues within the explicit simulation sphere, as well as histidine protonation patterns (both of which were validated by PROPKA 3.0 (refs. 70,71) and visual inspection), can be found in Supplementary Table 7. Each system was simulated in 30 replicas of 30-ns equilibration, with 5-kcal mol $^{-1}$  Å $^{-2}$  distance-based harmonic restraints applied between the substrate hydrogen donor carbon and the acceptor oxygen of Asp162. Each equilibration was followed by 10.2 ns of EVB simulations (200-ps window over 51 discrete EVB windows), carried out without the distance restraint applied, leading to a cumulative 612 ns of EVB simulation time per system (including 'in' and 'out' substrate conformations), and 3.6 μs of EVB equilibration time and 1.2 μs of EVB simulation time across all systems studied in this work (4.8 μs of simulation time in total). The corresponding r.m.s.d. values of the equilibration phase (calculated with the QCalc6 module of Q6) are shown in Extended Data Fig. 8a,b. We note that in one of

# Article

the initial 30 EVB trajectories for Des27.7 with the substrate in the out conformation, we observed active-site distortion with the catalytic Asp moving into a non-reactive conformation. This trajectory was excluded from further analysis, with an extra trajectory being run to create a full set of 30 replicas.

Representative stationary points for the KE reaction catalysed by Des27, extracted from EVB simulations of this system, are shown in Extended Data Fig. 8c,d. To extract the conformations representing each stationary point, all 30 replicas were evaluated together. The MDTraj software (version 1.10.0) $^{85}$  was applied to convert the trajectories to a CPPTRAJ compatible format, and clustering was performed based on the r.m.s.d. of the substrate heavy atoms, using the average linkage clustering method, with an  $\varepsilon$  value of 0.75. We note that the key stationary points for Des27.7 are visually similar to those for Des27. Sample input files, parameter files, starting structures and simulation snapshots have all been made available on Zenodo at https://doi.org/10.5281/zenodo.14563437 (ref. 73).

Simulation analysis. Unless otherwise stated, all MD analyses were performed using the CPPTRAJ module $^{86}$  of AmberTools24 (ref. 87). Trajectory frames were extracted every 400 ps, and results (where applicable) are reported as averages and standard deviations over  $5 \times 1 - \mu s$  trajectories per system. The fractions of unbound and bound modes during the simulations were determined by counting trajectory frames. A bound mode was defined on the basis of the distance between the ligand and the centre of mass of the active site, including residues 54, 84, 86, 92, 136, 162, 183 and 236. A threshold of  $4\AA$  was defined to classify the frames into unbound or bound. Unbound modes have left the active-site pocket, but not necessarily dissociated from the protein itself (sampling non-productive conformations out of the active site). The substrate orientation was defined using the distance between the  $\mathrm{C}_{\alpha}$ -atom of residue Leu41 and the N1 and N2 atoms of the substrate. Conformations with a Leu41-N1 distance between 0 and  $15\AA$  and L41-N2 distance between 15 and  $20\AA$  were classified as 'out', and otherwise as 'in'. Pocket volumes of Des27 and Des27.7 systems were calculated using MDPocket $^{88,89}$ , with snapshots taken every 4 ns of the simulations for unbound systems. Additionally, the volume of the ligand was calculated using the mol_volume package in VMD $^{90}$ . Finally, PyMOL was used for all visualization analyses.

# Reporting summary

Further information on research design is available in the Nature Portfolio Reporting Summary linked to this article.

# Data availability

All data generated and analysed during the study are available within the paper and its Supplementary Information. The crystal structures of Des27.7, R2.Des39 and R2.Des49 are deposited in the Protein Data Bank (PDB) under accession codes 9HVB, 9HVH and 9HVG, respectively. The crystal structures for all IGPS enzymes are available through the PDB with accession codes 1LBF, 1I4A, 1JCM, 1VC4 and 4FB7.

# Code availability

Custom Python scripts, RosettaScripts<sup>91</sup>, command lines, Jupyter notebooks and datasets used for de novo enzyme design are available at https://github.com/Fleishman-Lab/denovoKemp. Code and specifications used for MD analysis are available at Zenodo (https://doi.org/10.5281/zenodo.14563437)<sup>73</sup>.

56. Li, W., Jaroszewski, L. & Godzik, A. Clustering of highly homologous sequences to reduce the size of large protein databases. Bioinformatics 17, 282-283 (2001).  
57. Jumper, J. et al. Highly accurate protein structure prediction with AlphaFold. Nature 596, 583-589 (2021).

58. Mirdita, M. et al. ColabFold: making protein folding accessible to all. Nat. Methods 19, 679-682 (2022).  
59. Barber-Zucker, S. et al. Stable and functionally diverse versatile peroxidases designed directly from sequences. J. Am. Chem. Soc. 144, 3564-3571 (2022).  
60. Richter, F., Leaver-Fay, A., Khare, S. D., Bjelic, S. & Baker, D. De novo enzyme design using Rosetta3. PLoS ONE 6, e19230 (2011).  
61. Ribeiro, A. J. M. et al. Mechanism and Catalytic Site Atlas (M-CSA): a database of enzyme reaction mechanisms and active sites. Nucleic Acids Res. 46, D618-D623 (2018).  
62. Alford, R. F. et al. The Rosetta all-atom energy function for macromolecular modeling and design. J. Chem. Theory Comput. 13, 3031-3048 (2017).  
63. Elmsley, P., Lohkamp, B., Scott, W. G. & Cowtan, K. Features and development of Coot. Acta Crystallogr. D Biol. Crystallogr. 66, 486-501 (2010).  
64. Adams, P. D. et al. PHENIX: a comprehensive Python-based system for macromolecular structure solution. Acta Crystallogr. D Biol. Crystallogr. 66, 213-221 (2010).  
65. Williams, C. J. et al. MolProbity: more and better reference data for improved all-atom structure validation. Protein Sci. 27, 293-315 (2018).  
66. Woods, R. J. & Chappelle, R. Electrostatic potential atomic partial charges for condensed-phase simulations of carbohydrates. J. Mol. Struct. 527, 149-156 (2000).  
67. Wang, J., Wang, W., Kollman, P. A. & Case, D. A. Automatic atom type and bond type perception in molecular mechanical calculations. J. Mol. Graph. Model. 25, 247-260 (2006).  
68. Frisch, M. J. et al. Gaussian 16, Revision B.01 (Gaussian, 2016).  
69. Wang, J., Wolf, R. M., Caldwell, J. W., Kollman, P. A. & Case, D. A. Development and testing of a general amber force field. J. Comput. Chem. 25, 1157-1174 (2004).  
70. Olsson, M. H. M., Søndergaard, C. R., Rostkowski, M. & Jensen, J. H. PROPKA3: consistent treatment of internal and surface residues in empirical pKa predictions. J. Chem. Theory Comput. 7, 525-537 (2011).  
71. Sondergaard, C. R., Olsson, M. H. M., Rostkowski, M. & Jensen, J. H. Improved treatment of ligands and coupling effects in empirical calculation and rationalization of pKa values. J. Chem. Theory Comput. 7, 2284-2295 (2011).  
72. Izadi, S., Anandakrishnan, R. & Onufriev, A. V. Building Water Models: A Different Approach. J. Phys. Chem. Lett. 5, 3863-3871 (2014).  
73. Listov, D. et al. Complete computational design of high-efficiency Kemp elimination enzymes. Zenodo https://doi.org/10.5281/zenodo.14563437 (2025).  
74. Case, D. A. et al. Amber 2025 (Univ. California, San Francisco, 2025).  
75. Tian, C. et al. Ff19SB: amino-acid-specific protein backbone parameters trained against quantum mechanics energy surfaces in solution. J. Chem. Theory Comput. 16, 528-552 (2020).  
76. Schneider, T. & Stoll, E. Molecular-dynamics study of a three-dimensional one-component model for distortive phase transitions. Phys. Rev. B 17, 1302-1322 (1978).  
77. Berendsen, H. J. C., Postma, J. P. M., Van Gunsteren, W. F., DiNola, A. & Haak, J. R. Molecular dynamics with coupling to an external bath. J. Chem. Phys. 81, 3684-3690 (1984).  
78. Ryckaert, J.-P., Ciccotti, G. & Berendsen, H. J. C. Numerical integration of the Cartesian equations of motion of a system with constraints: molecular dynamics of  $n$ -alkanes. J. Comput. Phys. 23, 327-341 (1977).  
79. Hopkins, C. W., Le Grand, S., Walker, R. C. & Roitberg, A. E. Long-time-step molecular dynamics through hydrogen mass repartitioning. J. Chem. Theory Comput. 11, 1864-1874 (2015).  
80. Bauer, P. et al. Q6: a comprehensive toolkit for empirical valence bond and related free energy calculations. SoftwareX 7, 388-395 (2018).  
81. Kaminski, G. A., Friesner, R. A., Tirado-Rives, J. & Jorgensen, W. L. Evaluation and reparametrization of the OPLS-AA force field for proteins via comparison with accurate quantum chemical calculations on peptides. J. Phys. Chem. B 105, 6474-6487 (2001).  
82. Jorgensen, W. L., Chandrasekhar, J., Madura, J. D., Impey, R. W. & Klein, M. L. Comparison of simple potential functions for simulating liquid water. J. Chem. Phys. 79, 926-935 (1983).  
83. King, G. & Warshel, A. A surface constrained all-atom solvent model for effective simulations of polar solvents. J. Chem. Phys. 91, 3647-3661 (1989).  
84. Lee, F. S. & Warshel, A. A local reaction field method for fast evaluation of long-range electrostatic interactions in molecular simulations. J. Chem. Phys. 97, 3100-3107 (1992).  
85. McGibbon, R. T. et al. MDTraj: a modern open library for the analysis of molecular dynamics trajectories. Biophys. J. 109, 1528-1532 (2015).  
86. Roe, D. R. & Cheatham, T. E. 3rd PTRAJ and CPPTRAJ: software for processing and analysis of molecular dynamics trajectory data. J. Chem. Theory Comput. 9, 3084-3095 (2013).  
87. Case, D. A. et al. AmberTools. J. Chem. Inf. Model. 63, 6183-6191 (2023).  
88. Schmidtke, P., Bidon-Chanal, A., Luque, F. J. & Barril, X. MDPocket: open-source cavity detection and characterization on molecular dynamics trajectories. Bioinformatics 27, 3276-3285 (2011).  
89. Wagner, J. R. et al. POvME 3.0: software for mapping binding pocket flexibility. J. Chem. Theory Comput. 13, 4584-4592 (2017).  
90. Humphrey, W., Dalke, A. & Schulten, K. VMD: visual molecular dynamics. J. Mol. Graph. 14, 33-38 (1996).  
91. Fleishman, S. J. et al. RosettaScripts: a scripting language interface to the Rosetta macromolecular modeling suite. PLoS ONE 6, e20161 (2011).

Acknowledgements We thank D. Hilvert for discussions and R. Lipsh-Sokolik, Z. Avizemer, A. Tennenhouse and O. Khersonsky for critical reading. We also thank O. Khersonsky, M. Goldsmith and M. Ovadis for technical help. This work was funded by the Volkswagen Foundation grant no. 94747 (S.J.F.), the Israel Science Foundation grant no. 1844 (S.J.F.), the European Research Council through Consolidator and Advanced Award grants no. 815379 and no. 101140394 (S.J.F.), the European Innovation Council Pathfinder grant no. 101129798, W-BioCat (S.J.F.), the Institute for Environmental Sustainability at the Weizmann Institute of Science (S.J.F.), the Knut and Alice Wallenberg Foundation (S.C.L.K.), the Sven and Lily Lawski Foundation (G.H.) and a donation in memory of Sam Switzer (S.J.F.). We acknowledge the

National Academic Infrastructure for Supercomputing in Sweden (NAISS), partially funded by the Swedish Research Council through grant agreement no. 2022-06725, for awarding this project access to the LUMI supercomputer, owned by the EuroHPC Joint Undertaking and hosted by CSC (Finland) and the LUMI consortium, as well as the Tetralith supercomputer at NSC Linköping. This work used the Hive cluster, which is supported by the National Science Foundation under grant no. 1828187, access to which was provided by the Partnership for an Advanced Computing Environment (PACE) at the Georgia Institute of Technology, Atlanta, GA, USA. G.H. acknowledges KIFU for awarding access to a resource based in Hungary (Komondor HPC). S.C.L.K. is the Georgia Research Alliance - Vasser Wooley Chair of Molecular Design at Georgia Tech.

Author contributions D.L. and S.J.F. conceived the idea. D.L. developed the de novo design algorithm with help from S.Y.H. D.L. performed expression, purification and biochemical characterization. S.H.-R. performed crystallization experiments and O.D. determined crystal

structures, E.V., G.H. and A.B. performed formal analysis, investigations and visualizations. S.J.F. and S.C.L.K. were responsible for funding acquisition, methodology, supervision, and reviewing and editing the manuscript. D.L. and S.J.F. wrote the paper with input from all authors.

Competing interests The authors declare no competing interests.

# Additional information

Supplementary information The online version contains supplementary material available at https://doi.org/10.1038/s41586-025-09136-2.

Correspondence and requests for materials should be addressed to Sarel J. Fleishman.

Peer review information Nature thanks Hans Bunzel and the other, anonymous, reviewer(s) for their contribution to the peer review of this work. Peer reviewer reports are available.

Reprints and permissions information is available at http://www.nature.com/reprints.

![](images/7d4baad41e78ba4139b5c9ca1399073bba3f187c1650a7641cb4ad1c162bc827.jpg)

![](images/f36193842aad332154e31b74626ff3e6a64757a3a9ca65dff311b14a2c669e60.jpg)

![](images/1410b437e278818a2c7ba21a3a7e64f560bc9ea6b99cb7164612ce35ec40abfb.jpg)

![](images/ef0e213d4e3c23152739dc83383cd42dcdbb14510faf87b673a18ce2f0bfdaa6.jpg)

![](images/36663d9c8a6e5a3c0a497b224060edf6efffc1bae381335aebfd1308e7c9d3b0.jpg)

![](images/9d3ead5180397f356593c34bbc6e70d91b671413e5b51e0e44cafd056a1916e1.jpg)  
Extended Data Fig.1|Expression and stability of the initial design round. a. 66 designs were solubly expressed. High-functioning designs were expressed independently 2-5 times; otherwise, protein expression was performed once.

![](images/4efc024dadf137114c7d022658b77afe25982b110bbd994d4dd516b6f9f7ca27.jpg)  
For gel source data, see Supplementary Data1. b. Temperature melts of representative cooperatively folded (left) and unfolded (right) designs. All temperature melts are performed in technical duplicates.

![](images/6664b9aa70728d064ac429de77fda55cb257a1b3fd2df2270c8cf4a75003805e.jpg)

![](images/0ff3654e016dda3e064d2ce97631e5ddd784bfa1e57135a87c215388070cecca.jpg)

![](images/64965f260f64af2864746d3c58a05d629ee7818daf64c0b7ffb3a9346269489f.jpg)  
Extended Data Fig. 2 | Representative Michaelis-Menten plots. The data were fitted to the Michaelis-Menten equation  $\upsilon_{0} = k_{\mathrm{cat}}[\mathrm{E}]_{0}[\mathrm{S}]_{0} / ([\mathrm{S}]_{0} + K_{\mathrm{M}})$ . When substrate saturation could not be attained due to limited substrate solubility, the data were fitted to the linear region of the Michaelis-Menten model and

![](images/d0151081a4e1255e4a8f129cbbc179e8df04c5166e6fba5852cbbaa51c82e390.jpg)  
$\mathrm{v_0 = [S]_0[E]_0k_{cat} / K_M}$ , and  $k_{\mathrm{cat}} / K_{\mathrm{M}}$  were deduced from the slope. Kinetic experiments were performed for all functional designs in this study with at least two technical replicates, and high-functioning designs were further evaluated with 2-5 biological replicates. Data presented are mean of 2 technical repeats.

<table><tr><td colspan="2">Score 196 bits(499)</td><td>Expect Method 7e-58</td><td>Compositional matrix adjust.</td><td>Identities 118/259(46%)</td><td>Positives 168/259(64%)</td><td>Gaps 7/259(2%)</td><td></td></tr><tr><td rowspan="2">Query Sbct</td><td>2</td><td rowspan="2" colspan="5">PSALDAIVADVVEDVAAREAVVPFDEIKERAARAPPPRDVLAALRAPGVGIIAYVLRKSP .V..S..DG....L.V...A.D....R....K.A..H....M.T....I.V....EVK.R..</td><td>61</td></tr><tr><td>10</td><td>69</td></tr><tr><td rowspan="2">Query Sbct</td><td>62</td><td rowspan="2" colspan="5">SGLDVE--RDPIEYAKT-AEKYAVVALVVITDEKYHNGSYEDLEKIRSAVDIPVICFDFIV .KG.LATIS...A.L.ASY...GG.RVIS.L.EQRRFH...LA...DAV.A....ILRK....</td><td>118</td></tr><tr><td>70</td><td>129</td></tr><tr><td rowspan="2">Query Sbct</td><td>119</td><td rowspan="2" colspan="5">DPYQIYLARAYQADAIVLILSVLDDEQYRQLAAVAHSLNMGVIVDVHTEEELERALKAGA S....VHE....HG..LVL...VAA.EQNVLVA.LDRVE..G.TAL.E....AD....E....</td><td>178</td></tr><tr><td>130</td><td>189</td></tr><tr><td rowspan="2">Query Sbct</td><td>179</td><td rowspan="2" colspan="5">EIIGIVNQDLKTFEVDRNTAERLGRLARERGFTGVLLAIGGYSTKEELKSMRGL-FDAVV GL..VNARN.H.L....N.S---F.QI.PGLPNDVLRV.ES.VRGPGD.LTYA.WGA....L</td><td>237</td></tr><tr><td>190</td><td>246</td></tr><tr><td rowspan="2">Query Sbct</td><td>238</td><td colspan="5">IGESLMRPAPDPEKAIRELV 256</td><td></td></tr><tr><td>247</td><td colspan="5">V..G.VTSG..QS.V.S.. 265</td><td></td></tr></table>

Extended Data Fig. 3 | Protein BLAST search using the Des27.7 sequence as query against the NCBI "nr" database. Top hit in nr. Mutations are in red, hyphens indicate insertions and deletions.

![](images/4806b65dbc616dff47f136d74ba89730834c21a836c947a5fdfe5df554bbe6d5.jpg)  
a

![](images/a40dd9e157da64d46c1975975439ecc461cc2d414e0284ba099beef87d7f68cd.jpg)

![](images/ed189ac1000607934cdebd996d649c7495fac23e955107bff07b194b95d12f4d.jpg)

![](images/2b8989326c295a31267256613ca7da7715b12aa5dcb68a97137e7bb9db76b180.jpg)  
b

![](images/6418d896a20bf119dc625b24561247518312467facde74420999cef4645d844f.jpg)  
c

![](images/b1766cd93c5679513d4a0e93847756592bd650f52614031cd7edcc3044a7a493.jpg)  
d

![](images/0306cc035e49eb4fa0278f5087dd8da75c4a636aa6b6be56cba545bef0394272.jpg)

![](images/76abd9f38133b99011636a87ffb5a70a537387aa8f9c2b39a4bec54beb4d3826.jpg)  
e  
Extended Data Fig. 4 | See next page for caption.

![](images/26b3eacfa0561df19cd91744664f39c42f8ea34eb6e99f13496a7ada43f5e9a9.jpg)

# Article

Extended Data Fig. 4 | Simulations of dynamics, Asp162 conformations, and active-site pocket volume of Des27 and Des27.7. a. Joint distribution of the Asp162 conformational space in the unbound state. Conformation sampled by the  $\chi_{1}$  and  $\chi_{2}$  dihedral angles of the Asp162 side chain along MD simulations of the Des27 and Des27.7. In Des27 there are three distinct metastable Asp162 conformations, which are illustrated in the right panel. The conformation numbers labeled on the plots correspond to the stick representations on the right, with 5-nitrobenzisoxazole depicted in white sticks for reference. b-c. Visual representation of the calculated active site pockets in b. Des27 and

c. Des27.7, using MDPocket isosurfaces. Yellow spheres represent the pocket volume. Asp162 is shown in sticks. Des27.7 exhibits an active site pocket that can better accommodate 5-nitrobenzisoxazole. d-e. Root mean square deviations (rmsd,  $\mathring{\mathrm{A}}$ ) of the  $C_{\alpha}$ -atoms from MD simulations. Data was collected every 400 ps from 5 replicas of  $1\mu s$  length each. The gray lines show the five individual runs, and the colored solid line shows a rolling average of the rmsd from all five replicas for each system. d. rmsd for unbound systems Des27 (left), Des27.7 (right) e. rmsd for bound systems Des27 (left), Des27.7 (right).

![](images/61c5a164dc8949a8095150548bff55d6a1d4b343d43aa4535c57de831f63e146.jpg)  
a

![](images/5cfef94b41e4a8c411a1ac18b67ddba85ca4565261d2925c35962e59f7a4b0d5.jpg)  
b

![](images/fa5368556172b75a118983633536e35b6c0ece37f1835d9ce534a55289f61ca9.jpg)

![](images/7a4bae3bf5f388d2cb7704afd9e4697a2ed13855c5071788f9cae6676d0a1e70.jpg)

![](images/313d59ac1475a7640849a47bf262b24bd2d10756119e97993b0cb61a2aa43d2a.jpg)

![](images/767adbc89238c60ba720625cc7c97a10556ad7522ad518fc12a93953a8bf6e75.jpg)

![](images/d6d9fc89bf57bd1680ed6286e25bf7927791276cf10d3114cbe08c7caeabc8f1.jpg)

![](images/6ac2740d49493e22fb7cce5acca24c466a52469be675dd800b64194665c108cd.jpg)

![](images/9a7edc5aa31b403fad4e850b6e7c9b3cc12286e83e60cd21f7c84e8204dd09c7.jpg)  
Extended Data Fig. 5 | Time evolution of the active site center of mass (COM) and ligand distance during total  $5 \times 1 \mu \mathrm{s}$  of MD simulations. a. Des27 and b. Des27.7. The dotted gray line at  $4 \AA$  marks the threshold for defining the ligand as being within the active site. In two out of ten replicas across the two systems,

![](images/1d0b6d3882ccfe9a6ff039bbc535a0c98730c78893b9bde92e66bdc2a40fce33.jpg)  
we observe ligand dissociation without rebinding towards the end of the trajectory on the timescale of our simulations; in a third, in the case of Des27.7, we observe substantial dissociation mid-trajectory with ligand rebinding within the simulation timeframes.

![](images/0ec141f17bd49d2f707ad93f65a05ce1164d375c8b4109be656941670d668f8c.jpg)

![](images/ec1c2ea64455b6a710edc62e7e88452f68e2a3ea855958f2225e93ba5558c857.jpg)

![](images/92ca99225fddf33bbf71f31a15ed5c91b2811ebeae5c4bb0049b7d4e36006bbc.jpg)

# Extended Data Fig. 6 | Model and crystallographic structure of Des27.7,

Des39 and Des49. The substrate, 5-nitrobenzisoxazole, in yellow sticks. Loop regions in wheat represented misfolded/missing regions in the experimentally determined structure. a. Des27.7 model. b. Des27.7 crystallographic structure (PDB 9HVB). Wheat-colored loop corresponds to the one in panel b. c. R2.Des39 model. d. R2.Des39 crystallographic structure (PDB 9HVH). R2.Des39 crystallized as a dimer in the asymmetric unit with few crystallographic contacts that stabilize the wheat-colored loop. The two monomers are in pink and white. Wheat-colored loop corresponds to the one in panel c. e. Active site model

(blue sticks) vs structure (white sticks). rmsd between the active sites is  $0.61\AA$ . Catalytic Glu168 fits the modeled rotamer and there are only subtle rotameric changes in other active-site residues. These changes do not induce clashes with the modeled ligand. f. Asp62 stabilizes an alternative conformation in the crystal structure. Tyr97 (pink sticks) is from the second monomer. Colors as in panel d.g. R2.Des49 model. h. R2.Des49 crystallographic structure (PDB 9HVG). Wheat-colored loop corresponds to the one in panel g. i. Active-site model (blue sticks) vs structure (white sticks). rmsd between the active sites is  $0.82\AA$ . Trp115 acquires a rotamer different than modeled and might overlap with the ligand.

![](images/4b6c7b380cddd2e73bb4d9e0c489ff854e1e6915bb7832ff4a17b6f605668016.jpg)

![](images/c050cf19414f34f5ebd2b5421852409f4498aa5da50dfc80c3bdf8c7a91985b7.jpg)

# Extended Data Fig.7 | Comparison of substrate-bound and unbound

structure of Des27.7 Phe113Leu. a. A slight sidechain conformational change is observed, with an rmsd of 0.28 Å between the substrate-bound and unbound models of Des27.7 at position 113. b. No sidechain shift is observed in the case of Des27.7 Leu113. White sticks represent the substrate bound model, wheat sticks represent the unbound model, blue sticks represent unbound crystal structure.

![](images/e4e22b4257560d71ab41735aeb846b351f92b6eccdc7e9e9f7e34c40377bb603.jpg)  
a

![](images/2612a5175e6b2bb02221f70d570ca4c2c0e287509dc2c66ba0de84eedc957bc9.jpg)

![](images/597142c42b467a894bd1319dc15864b53b016f009dbbb72dd94bdeebaad11ddd.jpg)  
b

![](images/03256ad2ed9f72e9d986c00eace8fd1bb735083af0eea5a7a2c0ef99c5c94edd.jpg)

![](images/70886d1b0d98343b62bb4d55ed5d1b68d9435217765ea303c05b2576d5e8df75.jpg)  
c

![](images/10bde03053b0691488ae09a8634af83f91655a6b2e28c6127e2a0865b3fc28e4.jpg)

![](images/7f86c1fbde75815af1708d921ba0a8810749e963c70b18053504205698189416.jpg)

![](images/d4f7956a0c3e9cb517c609256c642c81896a1cdde5c22fb9b2194627347d6141.jpg)  
d

![](images/ed888a72f8c551bd638dfa895aaca4e1d5ab7b5227eb05a0227378be73ed4584.jpg)  
Extended Data Fig. 8 | EVB equilibration dynamics and representative structures of the Des27 system. a-b Root mean square deviations (rmsd, Å) of all solute atoms of the Des27 and Des27.7 calculated for the equilibration phase prior to our EVB simulations. Data were collected every 10 ps from the initial equilibration runs and shown as averages and standard deviations over ten individual 25 ns MD simulations per system (i.e., 750 ns cumulative simulation time per system). The average rmsd per system is denoted by the colored solid line, and the standard deviations per point over all trajectories are illustrated by the shaded area on each plot. a. rmsd for EVB equilibration from "out" substrate conformation. b. rmsd for EVB equilibration from "in" substrate

![](images/52e3e8efa0c6954cd06faea5efc727d891e033099c9a1d35a1884884d11108d2.jpg)  
conformation. c-d EVB Representative structures of the Des27 system. c. For the "in" ligand conformation. d. For the "out" ligand conformation. Michaelis complex (MC, left panel), transition state (TS, middle panel), and product complex (PC, right panel) for the KE reaction catalyzed by this enzyme, extracted from EVB trajectories of this reaction. Structures were selected based on clustering analysis. The clustering was performed at the MC, TS and PC independently, in order to obtain representative structures for each state. Donor-acceptor distances (Å) are shown for each stationary point. These values are averages of the snapshots taken every 5 ps of the trajectory, determined based on the combined evaluation of 30 replicas.

Extended Data Table 1 | Apparent thermal stability and catalytic parameters of designed Kemp eliminases  

<table><tr><td></td><td>kcat(s-1)</td><td>KM(mM)</td><td>kcat/KM(M-1s-1)</td><td>Tm(°C)</td></tr><tr><td>Des27</td><td>0.07 ± 0.02</td><td>0.5 ± 0.05</td><td>131 ± 37</td><td>79</td></tr><tr><td>Des27.1</td><td>n.c.</td><td>n.c.</td><td>344 ± 94</td><td>73</td></tr><tr><td>Des27.2</td><td>n.c.</td><td>n.c.</td><td>21</td><td>83</td></tr><tr><td>Des27.3</td><td>1.40</td><td>1.00</td><td>1,294</td><td>81</td></tr><tr><td>Des27.4</td><td>0.03</td><td>0.78</td><td>59 ± 30</td><td>82</td></tr><tr><td>Des27.5</td><td>n.c.</td><td>n.c.</td><td>54 ± 4</td><td>83</td></tr><tr><td>Des27.6</td><td>n.c.</td><td>n.c.</td><td>90 ± 49</td><td>84</td></tr><tr><td>Des27.7</td><td>2.85 ± 1.20</td><td>0.22 ± 0.06</td><td>12,696 ± 1738</td><td>85</td></tr><tr><td>Des27.9</td><td>3.10 ± 0.14</td><td>1.55 ± 0.64</td><td>2,136 ± 692</td><td>82</td></tr><tr><td>Des27.10</td><td>n.c.</td><td>n.c.</td><td>327 ± 129</td><td>81</td></tr><tr><td>Des27.11</td><td>0.64 ± 0.23</td><td>0.89 ± 0.09</td><td>718 ± 183</td><td>80</td></tr><tr><td>Des27.12</td><td>5.15 ± 2.47</td><td>1.30 ± 0.28</td><td>3,837 ± 864</td><td>80</td></tr><tr><td>Des27.13</td><td>2.45 ± 1.48</td><td>1.15 ± 0.21</td><td>2,014 ± 907</td><td>86</td></tr><tr><td>De61</td><td>0.3</td><td>1.3</td><td>213</td><td>65</td></tr><tr><td>Des61.1</td><td>0.85 ± 0.02</td><td>0.27 ± 0.06</td><td>3,205 ± 555</td><td>63</td></tr><tr><td>Des61.2</td><td>0.65</td><td>0.48</td><td>1,347</td><td>58</td></tr><tr><td>Des61.3</td><td>0.6</td><td>0.76</td><td>770</td><td>70</td></tr><tr><td>Des61.4</td><td>n.d.</td><td>n.d.</td><td>n.d.</td><td>67</td></tr><tr><td>Des61.5</td><td>n.c.</td><td>n.c.</td><td>542</td><td>62</td></tr><tr><td>Des61.6</td><td>0.77</td><td>0.43</td><td>1,778</td><td>58</td></tr><tr><td>R2.Des39</td><td>n.c.</td><td>n.c.</td><td>92</td><td>81</td></tr><tr><td>R2.Des39.2</td><td>n.c.</td><td>n.c.</td><td>298 ± 58</td><td>81</td></tr><tr><td>R2.Des39.2.1</td><td>n.c.</td><td>n.c.</td><td>1,136</td><td>n.m.</td></tr><tr><td>R2.Des39.2.17</td><td>n.c.</td><td>n.c.</td><td>1,121</td><td>n.m.</td></tr><tr><td>R2.Des39.2.18</td><td>n.c.</td><td>n.c.</td><td>2,044 ± 163</td><td>n.m.</td></tr><tr><td>MA</td><td>n.d.</td><td>n.d.</td><td>n.d.</td><td>60</td></tr><tr><td>MA + PROSS</td><td>n.d.</td><td>n.d.</td><td>n.d.</td><td>71</td></tr><tr><td>MA + active site</td><td>2.4 ± 1</td><td>0.80 ± 0.23</td><td>2,911 ± 642</td><td>62</td></tr><tr><td>MA+ PROSS + active site</td><td>3.8 ± 1</td><td>0.34 ± 0.06</td><td>11,531 ± 4,323</td><td>79</td></tr><tr><td>Des27.7 D162A</td><td>n.d.</td><td>n.d.</td><td>n.d.</td><td>&gt;100</td></tr><tr><td>Des27.7 F113M</td><td>6.7 ± 6</td><td>0.72 ± 0.1</td><td>11,511 ± 8,971</td><td>85</td></tr><tr><td>Des27.7 F113L</td><td>30.0 ± 8</td><td>0.25 ± 0.03</td><td>123,274 ± 40,707</td><td>84</td></tr></table>

$^{*}$ n.c. not calculable; n.d. not detectable; n.m. not measured; MA-modular assembly.  
All kinetic measurements were obtained at  $25^{\circ}\mathrm{C}$  and  $\mathsf{pH}7.3$  Data are means  $\pm \mathrm{SD}$  of 2-5 biological replicates; all measurements in technical duplicates.

Extended Data Table 2 | Data collection and refinement statistics (molecular replacement)  

<table><tr><td></td><td>Des27.7</td><td>R2.Des39</td><td>R2.Des49</td></tr><tr><td colspan="4">Data collection</td></tr><tr><td>Space group</td><td>P 61</td><td>P 21</td><td>C 2 2 21</td></tr><tr><td colspan="4">Cell dimensions</td></tr><tr><td>a, b, c (Å)</td><td>98.54, 98.54, 40.48</td><td>48.84 69.55 79.60</td><td>48.53, 88.94, 131.18</td></tr><tr><td>a, b, g (°)</td><td>90.00, 90.00, 120.00</td><td>90.00, 101.04, 90.00</td><td>90.00, 90.00, 90.00</td></tr><tr><td>Resolution (Å)</td><td>25.23-2.0 (2.07-2.00)*</td><td>21.24-2.1 (2.17-2.10)</td><td>21.06-1.9 (1.97-1.90)</td></tr><tr><td>Rmerge</td><td>0.114 (0.507)</td><td>0.104 (0.377)</td><td>0.066 (0.384)</td></tr><tr><td>I/sI</td><td>19.7 (6.0)</td><td>17.6 (4.3)</td><td>26.2 (4.0)</td></tr><tr><td>Completeness (%)</td><td>99.86 (100.00)</td><td>98.47 (99.97)</td><td>99.50 (100.00)</td></tr><tr><td>Redundancy</td><td>15.0 (16.4)</td><td>6.6 (6.0)</td><td>6.9 (6.6)</td></tr><tr><td colspan="4">Refinement</td></tr><tr><td>Resolution (Å)</td><td>2.0</td><td>2.10</td><td>1.90</td></tr><tr><td>No. reflections</td><td>15,395</td><td>30,227</td><td>22,668</td></tr><tr><td>Rwork / Rfree</td><td>0.1915 / 0.2419</td><td>0.2034 / 0.2556</td><td>0.1975 / 0.2591</td></tr><tr><td>No. atoms</td><td>1837</td><td>4205</td><td>2159</td></tr><tr><td>Protein</td><td>1726</td><td>3939</td><td>2013</td></tr><tr><td>Ligand/ion</td><td>10</td><td>0</td><td></td></tr><tr><td>Water</td><td>101</td><td>266</td><td>146</td></tr><tr><td colspan="4">B-factors</td></tr><tr><td>Protein</td><td>24.06</td><td>28.77</td><td>33.80</td></tr><tr><td>Ligand/ion</td><td>27.16</td><td></td><td></td></tr><tr><td>Water</td><td>29.20</td><td>29.22</td><td>41.01</td></tr><tr><td colspan="4">R.m.s. deviations</td></tr><tr><td>Bond lengths (Å)</td><td>0.007</td><td>0.008</td><td>0.007</td></tr><tr><td>Bond angles (°)</td><td>0.77</td><td>0.95</td><td>0.89</td></tr><tr><td colspan="4">Ramachandran</td></tr><tr><td>Favored (%)</td><td>97.73</td><td>96.72</td><td>98.02</td></tr><tr><td>Allowed (%)</td><td>2.27</td><td>2.70</td><td>1.98</td></tr><tr><td>Outliers (%)</td><td>0.00</td><td>0.58</td><td>0.00</td></tr></table>

*Values in parentheses are for highest-resolution shell.

# Reporting Summary

Nature Portfolio wishes to improve the reproducibility of the work that we publish. This form provides structure for consistency and transparency in reporting. For further information on Nature Portfolio policies, see our Editorial Policies and the Editorial Policy Checklist.

# Statistics

For all statistical analyses, confirm that the following items are present in the figure legend, table legend, main text, or Methods section.

n/a | Confirmed

The exact sample size  $(n)$  for each experimental group/condition, given as a discrete number and unit of measurement  
A statement on whether measurements were taken from distinct samples or whether the same sample was measured repeatedly  
The statistical test(s) used AND whether they are one- or two-sided Only common tests should be described solely by name; describe more complex techniques in the Methods section.  
A description of all covariates tested  
A description of any assumptions or corrections, such as tests of normality and adjustment for multiple comparisons  
A full description of the statistical parameters including central tendency (e.g. means) or other basic estimates (e.g. regression coefficient) AND variation (e.g. standard deviation) or associated estimates of uncertainty (e.g. confidence intervals)  
For null hypothesis testing, the test statistic (e.g.  $F$ ,  $t$ ,  $r$ ) with confidence intervals, effect sizes, degrees of freedom and  $P$  value noted Give  $P$  values as exact values whenever suitable.  
For Bayesian analysis, information on the choice of priors and Markov chain Monte Carlo settings  
For hierarchical and complex designs, identification of the appropriate level for tests and full reporting of outcomes  
Estimates of effect sizes (e.g. Cohen's  $d$ , Pearson's  $r$ ), indicating how they were calculated

Our web collection on statistics for biologists contains articles on many of the points above.

# Software and code

Policy information about availability of computer code

Data collection

Rosetta Modeling Suit 2021.07 (https://www.rosettacommons.org/)

ColabFold 1.3.0 (https://github.com/sokrypton/ColabFold)

Data analysis

All data analysis components and RosettaScripts files with detailed explanations can be found in https://github.com/Fleishman-Lab/ denovoKemp

All tools used for molecular dynamics are listed in methods section and are available at DOI: 10.5281/zenodo.14563437

All nano-DSF data were analysed using the Prometheus NT. 48 default software and nano-DSF graphs were made using Python 3.6.

For crystal structures molecular replacement and analysis were done using all standard crystallographic softwares mentioned in the methods section.

For MD simulations: Amber24

For EVB simulations: Q6

For protonation states: Propka 3.0

For partial charges: Gaussian 16 Rev. B.01

For MD analysis: CPPTRAJ: Trajectory Analysis. V6.18.1 from AmberTools24

For pocket volume: MDpocket from fpocket 4.2

For ligand volume: VMD version 1.9.4

For visualization: PyMOL 3.1.1

Python packages used:

matplotlib 3.1.0;

pandas 0.24.0;

SciPy 1.3.0;

Jupyter notebook 6.0.0;

pymol 2.5.2;

seaborn 0.9.0;

numpyy 1.16.4;

Biopython 1.74;

All graphs were made using Python 3.6.

For manuscripts utilizing custom algorithms or software that are central to the research but not yet described in published literature, software must be made available to editors and reviewers. We strongly encourage code deposition in a community repository (e.g. GitHub). See the Nature Portfolio guidelines for submitting code & software for further information.

# Data

Policy information about availability of data

All manuscripts must include a data availability statement. This statement should provide the following information, where applicable:

- Accession codes, unique identifiers, or web links for publicly available datasets  
- A description of any restrictions on data availability  
- For clinical datasets or third party data, please ensure that the statement adheres to our policy

All data generated and analyzed during the study are available within the paper and its Supplementary Information. The crystal structures of Des27.7, R2.Des39 and R2.Des49 are deposited in the PDB under accession codes 9HVB, 9HVH, and 9HVG respectively. The crystal structure for all IGPS enzymes is available through the Protein Data Bank (PDB; https://www.rcsb.org), with accession ID 1LBF, 1I4A, 1JCM, 1VC4, 4FB7.

# Research involving human participants, their data, or biological material

Policy information about studies with human participants or human data. See also policy information about sex, gender (identity/presentation), and sexual orientation and race, ethnicity and racism.

Reporting on sex and gender

N/A

Reporting on race, ethnicity, or other socially relevant groupings

N/A

Population characteristics

N/A

Recruitment

N/A

Ethics oversight

N/A

Note that full information on the approval of the study protocol must also be provided in the manuscript.

# Field-specific reporting

Please select the one below that is the best fit for your research. If you are not sure, read the appropriate sections before making your selection.

Life sciences

Behavioural & social sciences

Ecological, evolutionary & environmental sciences

For a reference copy of the document with all sections, see nature.com/documents/nr-reporting-summary-flat.pdf

# Life sciences study design

All studies must disclose on these points even when the disclosure is negative.

Sample size

Duplicates or greater as specified in figure legends. Sample size between 2-5 was chosen based on experimental effort required to express, produce and experimentally verify the biochemical parameters of the enzymes.

Data exclusions

In one of the 30 EVB trajectories for Des27.7 with the substrate in the out conformation, we observed active-site distortion with the catalytic Asp moving into a non-reactive conformation. This trajectory was excluded from further analysis, with an additional trajectory being run to create a full set of 30 replicas. Exclusion criteria were not pre-established.

Replication

All specified in the legends and methods section. Biochemical assays used 2-5 biological replicates. MD simulations employed 5-10 replicas; EVB simulations used 30 replicas.

Randomization

Randomization is not relevant to this study. In vitro biochemical assays did not involve treatment groups or subjective measurements

# Reporting for specific materials, systems and methods

We require information from authors about some types of materials, experimental systems and methods used in many studies. Here, indicate whether each material system or method listed is relevant to your study. If you are not sure if a list item applies to your research, read the appropriate section before selecting a response.

Materials & experimental systems  

<table><tr><td>n/a</td><td>Involved in the study</td></tr><tr><td>×</td><td>Antibodies</td></tr><tr><td>×</td><td>Eukaryotic cell lines</td></tr><tr><td>×</td><td>Palaeontology and archaeology</td></tr><tr><td>×</td><td>Animals and other organisms</td></tr><tr><td>×</td><td>Clinical data</td></tr><tr><td>×</td><td>Dual use research of concern</td></tr><tr><td>×</td><td>Plants</td></tr></table>

Methods  

<table><tr><td>n/a</td><td>Involved in the study</td></tr><tr><td>×</td><td>□ ChIP-seq</td></tr><tr><td>×</td><td>□ Flow cytometry</td></tr><tr><td>×</td><td>□ MRI-based neuroimaging</td></tr></table>

Plants  

<table><tr><td>Seed stocks</td><td>N/A</td></tr><tr><td>Novel plant genotypes</td><td>N/A</td></tr><tr><td>Authentication</td><td>N/A</td></tr></table>