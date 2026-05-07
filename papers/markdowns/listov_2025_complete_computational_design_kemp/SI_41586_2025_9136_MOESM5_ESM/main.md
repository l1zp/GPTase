# Complete computational design of high-efficiency Kemp elimination enzymes

Corresponding Author: Professor Sarel Fleishman

This file contains all reviewer reports in order by version, followed by all author rebuttals in order by version.

Version 1:

Reviewer comments:

Referee #1

(Remarks to the Author)
The manuscript by Listov et al. outlines a two-prone computational approach towards full in silico design of a Kemp eliminase with performance characteristics on par with enzymes found in nature.

Overall, the manuscript is very well written and scientifically sound. It marks a significant advance in our ability to build de novo biocatalysts and impresses with its rigorous analysis, both structurally and computationally, to arrive at a sound rationale for the observed functional gains. The authors should be commended for the additional work on the contributions of various design elements to the overall success of novel enzymes. It is also refreshing to see that enzymes still hold a few surprises despite the tremendously exciting advances in computational design as shown by the highly beneficial functional effects of F113L discovered during the analysis of the lead enzyme variant.

A few suggestions for minor changes:

• Abstract: the statement that the manuscript presents “a fully computational workflow for designing efficient enzymes… without requiring experimental optimization.” is inconsistent with the described work and needs revision. On page 4, the authors report the experimental testing of 73 variants which resulted in the identification of two leading designs, Des27 and Des61. These two variants were subsequently optimized with FuncLib, an optimization step that led to further experimental testing of multiple variants including the best performing Des27.7.

• Page 1 and 10: References to the authors’ own work as a milestone in enzyme design should be removed. The present work is excellent science and its significance will be recognized by others in the field in due time.

• Page 2: the statement that “no naturally occurring enzyme is known to catalyze this reaction.” is not accurate. Numerous natural enzymes with the ability to catalyze this reaction have been reported including aldoxime dehydratases by the Asano group which show high catalytic activity (https://doi.org/10.1002/cbic.201600596)

• Page 8: delete “frustrating” from the sentence. It is well known in the field that the introduction of mutations during directed evolution typically coincides with trade-offs amongst various performance characteristics. While the effect might frustrate novices to laboratory protein evolution, practitioners are well aware that these losses are temporary and recoverable in subsequent rounds without much drama.

(Remarks on code availability) not reviewed

Referee #2

(Remarks to the Author)

This article describes the generation and characterization of high efficiency enzymes for the model Kemp elimination reaction. While many Kemp eliminases have been designed using diverse approaches and this is a model reaction, the catalytic efficacies obtained by the authors rival those of many natural enzymes and are the highest for designed proteins obtained so far; these efficiencies were obtained using computational approaches only (rather than directed evolution or library screening). This latter point makes it a very impressive result, although the principles underlying Kemp elimination, a buried base residue, active site pre-organization, lack of substrate binding mode degeneracy, and entry-egress pathways etc. have been identified before. The highest efficiency enzyme came about in an unexpected manner (a "knockout" mutation of a key theozyme residue led to a remarkable increase in catalysis. On this point, while the authors are correct in identifying the possible reasons for why this may have occured, the increase is still serendipitous and it seems incorrect to assert as the authors do in the abstract that "[current] understanding of biocatalysis and protein structure-function relationships is sufficient for programming stable, high-efficiency, new-to-nature enzymes through a minimal experimental effort". This minor point aside, the work is very impressive and heroic in the scale of the effort. Thorough characterization of the contribution of the different elements of the design approach - backbone recombination of native enzymes, sequence design, and active site design has been made, and interesting observations of a lack of stability-activity trade-off have been revealed. I support publication of the manuscript in Nature.

(Remarks on code availability) I have not looked at the repository in detail but looks complete. Please ensure that everything is publicly available.

"These mutations are combined and threaded onto the input structure (protocol to be published)." Is this available in the repository?

Referee #3

(Remarks to the Author)

The manuscript by Listov et al. presents an impressive computational pipeline for the de novo design of high-efficiency Kemp eliminases. The authors demonstrate how the integration of modular backbone assembly, theozyme-guided activesite design, and global stabilization using PROSS and FuncLib can yield stable, catalytically proficient enzymes without the need for iterative experimental evolution. I believe this work is both important and impactful. Nevertheless, I have a few comments that I hope the authors will consider addressing prior to publication.

Major comments

1. If I understand the control experiment for modular assembly correctly (page 8), the authors do not clearly demonstrate that their backbone assembly strategy contributes meaningfully to design success. The designs generated from 1,200 AlphaFold2-modeled IGPS sequences—without modular assembly—produced a higher number of active variants (20 vs. 3) and showed similar catalytic efficiencies (kcat/KM). While the authors claim that modular assembly increases structural diversity and enriches for catalytically competent backbones, the data appear to suggest that equally successful, if not more successful, designs can be obtained using natural sequences alone. It is possible that I have misunderstood the experiment, and I would appreciate clarification. Along these lines, I note that for the designs presented in this section, only the best kcat/KM values are reported, making it impossible to assess whether catalytic rates (kcat) themselves differ between the two strategies.

2. The authors state that their best design exhibited a catalytic rate $( 3 0 \thinspace \mathsf { s } ^ { - 1 } )$ and efficiency on par with natural proton eliminases like ketosteroid isomerase (KSI) $( \mathsf { k c a t } / \mathsf { K m } = 5 \times 1 0 ^ { 5 } \mathsf { M } ^ { - 1 } \mathsf { s } ^ { - 1 }$ , $\mathsf { k c a t } = 9 \mathsf { s } ^ { - 1 }$ ). Unfortunately, KSI is substantially more active $( \mathsf { k c a t } = 2 \times 1 0 ^ { 5 } \mathsf { s } ^ { - 1 }$ , $k c a t / { \mathsf { K m } } = 4 \times 1 0 ^ { 8 } \mathsf { M } ^ { - 1 } \mathsf { s } ^ { - 1 }$ , Kim et al., Biochemistry 1999). This statement should be revised to reflect the much higher catalytic performance of KSI. It should also be noted that design and evolution have previously afforded Kemp eliminases with substantially higher kcat values (e.g., ${ \sf H G 3 . 1 7 }$ , $\mathsf { k c a t } = 7 0 0 \mathsf { s } ^ { - 1 }$ , Blomberg et al., Nature 2013). The best enzyme created by the authors remains at least an order of magnitude slower in terms of turnover rate. While I do not think these comparisons diminish the impressive accomplishments of the authors, a more nuanced discussion about the current limitations of computational enzyme design would be desirable—especially regarding the difficulty of designing enzymes that outperform the “average” enzyme (Bar-Even et al., Biochemistry 2011).

3. “Empirical valence bond (EVB) calculations of reaction free energies50 show similar energy profiles for both conformations, indicating that both are catalytically competent (Fig. 3E and Supplementary Table 4). Taken together, the MD and EVB calculations suggest that the experimentally measured results reflect the sum of both reaction modes with the “out” conformation (Fig. 3C) being occupied a greater fraction than the “in” conformation but the latter being slightly more reactive (Fig. 3E).”

While this statement is technically true, the error bars on the calculated activation barriers span up to 6 kcal/mol. Given this level of uncertainty, it is unclear whether the data robustly support the conclusion that both states are catalytically competent and that the “in” conformation is slightly more reactive.

Minor Remarks

4. “Despite increasing sophistication in protein design methods, computationally designed KEs exhibited low efficiencies (kcat/Km 1-420 M-1s-1, kcat 0.006-0.7 s-1)1,3 and required further experimental optimization to achieve catalytic efficiencies and rates comparable to natural enzymes (kcat/Km 105 M-1s-1, kcat 10 s-1 respectively)18.”

The catalytic parameters in the final brackets reflect those of “average” natural enzymes (Bar-Even et al., Biochemistry 2011). However, it is unclear from the text whether the stated values represent natural “average” enzymes or the performance of evolved Kemp eliminases, which can reach much higher rates (e.g., HG3.17, kca $: = 7 0 0 \mathtt { s } ^ { - 1 }$ ; Blomberg et al.,

Nature, 2013). It would be helpful if the authors could revise this sentence to avoid potential confusion and clearly indicate which benchmark is being referred to.

5. “Km reflects enzyme-substrate complex stability, indicating that these achievements are due to near-optimal molecular recognition”. It may be helpful to specify which molecular species are being recognized with near-optimal affinity. If I understand correctly, the authors intend to say that the substrate in its ground state is well-recognized (as reflected by the low Km), whereas the transition state is still suboptimally stabilized. If so, the sentence would benefit from rephrasing to clarify this distinction and avoid potential misunderstandings.

6. Fig. 1 Panel A: The transition state complex carries a net negative charge, which is not currently indicated in the figure. It would be helpful to add a negative sign (e.g., a “–” next to the double dagger).

7. “We started by examining whether modular assembly and design is essential for generating diverse backbones. Instead of applying modular assembly and design, we applied the subsequent steps of the workflow to 1,200 representative IGPSs that were modeled using AlphaFold2 (see Methods).”

This description is somewhat unclear. Does this mean the authors started from 1,200 natural IGPS sequences? If so, it would be important to state explicitly where these sequences come from and how they were selected. This point is particularly relevant as this experiment serves as a critical control to assess the necessity and relevance of the modular assembly strategy (see my first remark).

8. Can the authors please provide catalytic parameters and sequences of at least all active variants, and ideally all experimentally tested variants? For example, Des27 and Des61 are two of the three active designs from the initial screen, but the third active design is not discussed. Similarly, the AlphaFold-based design yielded 20 active variants; however, no sequences or kinetic parameters are reported for these. Including this data—either in the main text or as supplementary material—would greatly enhance reproducibility.

9. It would be helpful if the authors more carefully word the section in which they describe the contributions of individual steps during their design. For instance, in the sentence “As expected, combinatorial assembly and design alone (with 92 mutations to any natural protein) did not exhibit any KE activity,” it is not entirely clear what was done. If I understand correctly, the authors have reverted all mutations Des27.7 from PROSS and the active-site design? If so, it would be good to state this explicitly instead of only referring to “combinatorial assembly and design alone”. This ambiguity is present not only in this example but throughout the entire section.

(Remarks on code availability)

Version 2:

Reviewer comments:

Referee #3

(Remarks to the Author)
I would like to thank the authors for thoroughly addressing my concerns and congratulate them on their excellent work. I have no further comments and fully endorse their work for publication.

(Remarks on code availability)

Open Access This Peer Review File is licensed under a Creative Commons Attribution 4.0 International License, which permits use, sharing, adaptation, distribution and reproduction in any medium or format, as long as you give appropriate credit to the original author(s) and the source, provide a link to the Creative Commons license, and indicate if changes were made.

In cases where reviewers are anonymous, credit should be given to 'Anonymous Referee' and the source.

The images or other third party material in this Peer Review File are included in the article’s Creative Commons license, unless indicated otherwise in a credit line to the material. If material is not included in the article’s Creative Commons license and your intended use is not permitted by statutory regulation or exceeds the permitted use, you will need to obtain permission directly from the copyright holder.

To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0/

Dear Editor,

On behalf of all authors, I would like to thank you and the reviewers for the time you have taken to consider our manuscript and for the positive and comprehensive review. The comments helped us improve and balance the presentation, and we provide a point-by-point response to the comments below. The revised manuscript highlights all changes using Word Track Changes, as requested.

We hope the revised manuscript is satisfactory for publication in Nature.

With best regards,

Sarel Fleishman on behalf of all authors.

Referee #1

The manuscript by Listov et al. outlines a two-prone computational approach towards full in silico design of a Kemp eliminase with performance characteristics on par with enzymes found in nature.

Overall, the manuscript is very well written and scientifically sound. It marks a significant advance in our ability to build de novo biocatalysts and impresses with its rigorous analysis, both structurally and computationally, to arrive at a sound rationale for the observed functional gains. The authors should be commended for the additional work on the contributions of various design elements to the overall success of novel enzymes. It is also refreshing to see that enzymes still hold a few surprises despite the tremendously exciting advances in computational design as shown by the highly beneficial functional effects of F113L discovered during the analysis of the lead enzyme variant.

Thank you for appreciating the work.

A few suggestions for minor changes:

• Abstract: the statement that the manuscript presents “a fully computational workflow for designing efficient enzymes… without requiring experimental optimization.” is inconsistent with the described work and needs revision. On page 4, the authors report the experimental testing of 73 variants which resulted in the identification of two leading designs, Des27 and Des61. These two variants were subsequently optimized with FuncLib, an optimization step that led to further experimental testing of multiple variants including the best performing Des27.7.

Right. We revised the abstract to clarify that the workflow did not require large-scale screening of mutant libraries. That is one of the distinguishing factors of our work compared to previous ones where de novo enzymes reached high turnovers.

• Page 1 and 10: References to the authors’ own work as a milestone in enzyme design should be removed. The present work is excellent science and its significance will be recognized by others in the field in due time.

Thank you. We changed the references to two recent reviews of the field (one is ours, but it is comprehensive).

• Page 2: the statement that “no naturally occurring enzyme is known to catalyze this reaction.” is not accurate. Numerous natural enzymes with the ability to catalyze this reaction have been reported including aldoxime dehydratases by the Asano group which show high catalytic activity (https://doi.org/10.1002/cbic.201600596)

We thank the reviewer for noting this. Indeed, several natural enzymes have been shown to catalyze the Kemp elimination reaction. We revised the sentence to say that no natural enzyme has been evolved for this reaction.

• Page 8: delete “frustrating” from the sentence. It is well known in the field that the introduction of mutations during directed evolution typically coincides with trade-offs amongst various performance characteristics. While the effect might frustrate novices to laboratory protein evolution, practitioners are well aware that these losses are temporary and recoverable in subsequent rounds without much drama.

Thank you for this. We have deleted this.

# Referee #2

This article describes the generation and characterization of high efficiency enzymes for the model Kemp elimination reaction. While many Kemp eliminases have been designed using diverse approaches and this is a model reaction, the catalytic efficacies obtained by the authors rival those of many natural enzymes and are the highest for designed proteins obtained so far; these efficiencies were obtained using computational approaches only (rather than directed evolution or library screening). This latter point makes it a very impressive result, although the principles underlying Kemp elimination, a buried base residue, active site pre-organization, lack of substrate binding mode degeneracy, and entry-egress pathways etc. have been identified before.

Thank you for appreciating our work.

The highest efficiency enzyme came about in an unexpected manner (a "knockout" mutation of a key theozyme residue led to a remarkable increase in catalysis. On this point, while the authors are correct in identifying the possible reasons for why this may have occured, the increase is still serendipitous and it seems incorrect to assert as the authors do in the abstract that "[current] understanding of biocatalysis and protein structure-function relationships is sufficient for programming stable, high-efficiency, new-to-nature enzymes through a minimal experimental effort".

We agree. We have revised this sentence to remove the claims on understanding. We note, however, that the Phe Leu mutation was not serendipitous but designed by Rosetta; that is, it exhibits low energy according to our calculations. We certainly agree that a clearer definition of the contribution of residues to the theozyme would be necessary to demonstrate the understanding of biocatalysis to which our previous phrasing alluded. We have added that such advances are needed to enable programmable enzyme design as the final sentence of the Conclusions section.

Referee #2 (Remarks on code availability):

I have not looked at the repository in detail but looks complete. Please ensure that everything is publicly available.

Checked and yes. Thanks.

"These mutations are combined and threaded onto the input structure (protocol to be published)." Is this available in the repository?

We have now added the protocol to the repository and removed the parenthesised reference to a protocol to be published.

Referee #3 (Remarks to the Author):

The manuscript by Listov et al. presents an impressive computational pipeline for the de novo design of high-efficiency Kemp eliminases. The authors demonstrate how the integration of modular backbone assembly, theozyme-guided active-site design, and global stabilization using PROSS and FuncLib can yield stable, catalytically proficient enzymes without the need for iterative experimental evolution. I believe this work is both important and impactful. Nevertheless, I have a few comments that I hope the authors will consider addressing prior to publication.

Thank you for the positive and helpful comments.

Major comments

1. If I understand the control experiment for modular assembly correctly (page 8), the authors do not clearly demonstrate that their backbone assembly strategy contributes meaningfully to design success. The designs generated from 1,200 AlphaFold2-modeled IGPS sequences— without modular assembly—produced a higher number of active variants (20 vs. 3) and showed similar catalytic efficiencies (kcat/KM). While the authors claim that modular assembly increases structural diversity and enriches for catalytically competent backbones, the data appear to suggest that equally successful, if not more successful, designs can be obtained using natural sequences alone. It is possible that I have misunderstood the experiment, and I would appreciate clarification.

We clarified this paragraph based on the reviewer’s comments. While it is true that the designs generated from AlphaFold2-modeled natural sequences resulted in a higher absolute number of active variants, even following FuncLib design, the best were much less efficient than Des27.7. The revision takes a more balanced tone to explain that both strategies are useful, and that in the current implementation, modular assembly produced a better enzyme, potentially due to the greater structural diversity. We are continuing to develop modular assembly and will continue to compare its performance with that of the design of AlphaFold models of natural enzymes.

Along these lines, I note that for the designs presented in this section, only the best kcat/KM values are reported, making it impossible to assess whether catalytic rates (kcat) themselves differ between the two strategies.

We have now added the calculated $k _ { \tt c a t }$ values, where available, to Supplementary Table 1 (a separate Excel file). For many designs exhibiting low catalytic efficiencies $( k _ { \mathrm { { c a t } } } / K _ { \mathrm { { m } } } )$ , the substrate concentration at half-maximal activity could not be determined experimentally due to low substrate solubility. In these cases, we estimated $k _ { \mathrm { { c a t } } } / K _ { \mathrm { { m } } }$ from the initial slope of the Michaelis-Menten curve, rather than from full saturation kinetics (see Methods section- Activity assay and determination of kinetic parameters).

2. The authors state that their best design exhibited a catalytic rate $\left( 3 0 \thinspace \mathsf { S } ^ { - } \thinspace ^ { 1 } \right)$ and efficiency on par with natural proton eliminases like ketosteroid isomerase (KSI) $k c a t / \mathsf { K m } = 5 \times 1 0 ^ { 5 } \mathsf { M } ^ { - } \uparrow \mathsf { s } ^ { - }$ , ${ \mathsf { c a t } } = 9 ~ { \mathsf { s } } ^ { - }$ ¹). Unfortunately, KSI is substantially more active $( \mathsf { k c a t } = 2 \times 1 0 ^ { 5 } \mathsf { s } ^ { - } )$ , $\mathsf { k c a t / K m } = 4$ $\times 1 0 ^ { 8 } ~ \mathsf { M } ^ { - } ~ \overset { \cdot } { \mathsf { s } } ^ { - } ~ \overset { \cdot } { \iota }$ , Kim et al., Biochemistry 1999). This statement should be revised to reflect the much higher catalytic performance of KSI. It should also be noted that design and evolution have previously afforded Kemp eliminases with substantially higher kcat values (e.g., HG3.17, $\mathsf { k c a t } = 7 0 0 ~ \mathsf { s } ^ { - } ~ 1$ , Blomberg et al., Nature 2013). The best enzyme created by the authors remains at least an order of magnitude slower in terms of turnover rate. While I do not think these comparisons diminish the impressive accomplishments of the authors, a more nuanced discussion about the current limitations of computational enzyme design would be desirable— especially regarding the difficulty of designing enzymes that outperform the “average” enzyme (Bar-Even et al., Biochemistry 2011).

We thank the reviewer for pointing this out. We referenced KSI activity with a different substrate (5,10-estrene-3,17-dione) and agree that this can be misleading; we removed that sentence entirely. We also added more explicit references to two accomplished in vitro evolution campaigns of Kemp eliminases, including Blomberg, where we discuss the “median” enzyme parameters in the introduction.

3. “Empirical valence bond (EVB) calculations of reaction free energies show similar energy profiles for both conformations, indicating that both are catalytically competent (Fig. 3E and Supplementary Table 4). Taken together, the MD and EVB calculations suggest that the experimentally measured results reflect the sum of both reaction modes with the “out” conformation (Fig. 3C) being occupied a greater fraction than the “in” conformation but the latter being slightly more reactive (Fig. 3E).”

While this statement is technically true, the error bars on the calculated activation barriers span up to 6 kcal/mol. Given this level of uncertainty, it is unclear whether the data robustly support the conclusion that both states are catalytically competent and that the “in” conformation is slightly more reactive.

We agree with the reviewer about the standard deviation and overlap (standard deviations up to 2.4 kcal/mol). To validate whether these differences are statistically significant, we performed Shapiro-Wilk tests for normality on the Des27 and Des27.7 in/out conformations followed by a two-sample t-test comparing the in/out conformations to check for significance. In all cases, we observe normal distributions (σ values of ${ > } 0 . 0 5$ ). Further, the activation energy differences are significant only in Des27.7 and not in Des27 at a $p$ -value threshold of $5 \%$ . We have modified the text on pg. 6 to reflect this and included the statistical analysis in the captions of Figure 3 and Extended Data Table 3.

Finally, we note as an aside that when examining our trajectories again, we noticed one higher energy (21.9 kcal/mol) outlier in simulations of Des27.7 with the substrate in the out conformation. Excluding this outlier does not significantly impact the overall energetics, with an average activation free energy of $1 5 . 6 \pm 1 . 9$ kcal/mol with the outlier included, and $1 5 . 4 \pm$ 1.5 kcal/mol with the outlier removed. We examined the outlier and observed that the reason for the high energy was that during the EVB simulation, the catalytic aspartic acid somehow managed to move to a non-reactive position, hence the high activation energy. Because of this structural distortion, we have excluded this trajectory from further analysis and generated an additional EVB trajectory to keep a full set of 30 (new activation free energy $1 5 . 5 \pm 1 . 5$ kcal/mol over 30 trajectories). We have elaborated on this in the Methods (description of the EVB simulations) and updated Figure 3 and Extended Data Table 4 accordingly. We note that this update does not impact our overall results and conclusions.

Minor Remarks

4. “Despite increasing sophistication in protein design methods, computationally designed KEs exhibited low efficiencies (kcat/Km 1-420 M-1s-1, kcat 0.006-0.7 s-1)1,3 and required further experimental optimization to achieve catalytic efficiencies and rates comparable to natural enzymes (kcat/Km 105 M-1s-1, kcat 10 s-1 respectively)18.”

The catalytic parameters in the final brackets reflect those of “average” natural enzymes (Bar-Even et al., Biochemistry 2011). However, it is unclear from the text whether the stated values represent natural “average” enzymes or the performance of evolved Kemp eliminases, which can reach much higher rates (e.g., HG3.17, $\mathsf { k c a t } = 7 0 0 \mathsf { s } ^ { - } \mathsf { \Omega }$ ¹; Blomberg et al., Nature, 2013). It would be helpful if the authors could revise this sentence to avoid potential confusion and clearly indicate which benchmark is being referred to.

Right. We have clarified by referring to the “median” values observed in enzymes in nature.

5. “Km reflects enzyme-substrate complex stability, indicating that these achievements are due to near-optimal molecular recognition”. It may be helpful to specify which molecular species are being recognized with near-optimal affinity. If I understand correctly, the authors intend to say that the substrate in its ground state is well-recognized (as reflected by the low Km), whereas the transition state is still suboptimally stabilized. If so, the sentence would benefit from rephrasing to clarify this distinction and avoid potential misunderstandings.

We revised to clarify that low $K _ { \mathfrak { m } }$ reflects ground-state substrate binding, not transition-state stabilization, and to emphasize the distinction between binding and catalysis.

6. Fig. 1 Panel A: The transition state complex carries a net negative charge, which is not currently indicated in the figure. It would be helpful to add a negative sign (e.g., a “–” next to the double dagger).

Thank you. The equations were indeed imbalanced. We added the negative sign to the transition state and corrected the reaction by adding BH to the products. The revised reaction conserves matter and charge.

7. “We started by examining whether modular assembly and design is essential for generating diverse backbones. Instead of applying modular assembly and design, we applied the subsequent steps of the workflow to 1,200 representative IGPSs that were modeled using AlphaFold2 (see Methods).”

This description is somewhat unclear. Does this mean the authors started from 1,200 natural IGPS sequences? If so, it would be important to state explicitly where these sequences come from and how they were selected. This point is particularly relevant as this experiment serves as a critical control to assess the necessity and relevance of the modular assembly strategy (see my first remark).

The 1,200 sequences are natural homologs of IGPS that were found using BLAST against the nonredundant sequence database and the sequence of the PDB entry 1I4N as the query. We started with 4,381 IGPS homologs and clustered those using CD-HIT by $3 0 { - } 9 0 \%$ sequence identity to one another to obtain the 1,200 sequences for AlphaFold modeling. After filtering based on pLDDT scores, we retained 1,072 backbone structures. This is now stated explicitly in the Methods section, along with additional details on their selection and modeling. We kept this information in the Methods to avoid disrupting the flow of the main text.

8. Can the authors please provide catalytic parameters and sequences of at least all active variants, and ideally all experimentally tested variants? For example, Des27 and Des61 are two of the three active designs from the initial screen, but the third active design is not discussed. Similarly, the AlphaFold-based design yielded 20 active variants; however, no sequences or kinetic parameters are reported for these. Including this data—either in the main text or as supplementary material—would greatly enhance reproducibility.

Right. The data are provided in Supplementary Table 1 (an additional Excel file).

9. It would be helpful if the authors more carefully word the section in which they describe the contributions of individual steps during their design. For instance, in the sentence “As expected, combinatorial assembly and design alone (with 92 mutations to any natural protein) did not exhibit any KE activity,” it is not entirely clear what was done. If I understand correctly, the authors have reverted all mutations Des27.7 from PROSS and the active-site design? If so, it would be good to state this explicitly instead of only referring to “combinatorial assembly and design alone”. This ambiguity is present not only in this example but throughout the entire section.

We have revised the entire section to clearly specify which sets of mutations were included at each design stage, removing ambiguity around the contributions of combinatorial assembly, PROSS, and active-site design. You understood correctly that we reverted PROSS and the active-site pocket in that specific design. Thank you.
