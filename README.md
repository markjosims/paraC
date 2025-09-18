# tira_parser
Dataset and FST code for Tira morphological parsing

## Usage 
The Tira parser can perform morphological decomposition and analysis of Tira text. A simple analyzed sentence is given below,
where 'Sentence' corresponds to a transcription without any analysis or decomposition, 'Parse' is the morphologically decomposed
version of the same transcription and 'Gloss' is the morpheme-by-morpheme translation.

    | Sentence  | kúkù         | kə̀pɔ́                      | ɛ́nà           |
    | Parse     | kúkù         | kə̀-p-ɔ́                    | ɛ́nà           |
    | Gloss     | (Clg)Kuku    | Clg-beat-FV.Vent.Pfv      | hunted.animal |

Given the 'Sentence' row as input, the parser will output the 'Parse' and 'Gloss' rows.
The parser will need to account not just for concatenative morphology but also more complex processes such as tonal exponence.

    | Sentence  | lɛ̀ré  | lɛ̂ré      |
    | Parse     | lɛ̀ré  | <H>+lɛ̀ré  |
    | Gloss     | bowl  | bowl.LOC  |

Tone processes can also be long distance.
The parser will, ideally, be able to account for the fact that the initial high tone on \[kárɔ́gɛ́] /k-àr-ɔ́-gɛ́/
comes from the sentence-initial focus particle /àn/.

    | Sentence  | àn        | ɔ́ndì  | kárɔ́gɛ́                    | lúrnɔ̀             | kə̀r̀lɛ̀ɲí               | ŋɛ́n   |
    | Parse     | àn^<H>    | ɔ́ndì  | <H>+k-àr-ɔ́-gɛ́             | l-úrnɔ̀            | kə̀-r̀lɛ̀ɲ-í             | ŋɛ́n   |
    | Gloss     | FOC       | what  | Clg-say-FV.Vent.Pfv-Wh    | CLl-grandfather   | Clg-chase-FV.Vent.Pfv | dog   |

Tira is an under-studied language, and the data to be processed come from various stages of the lifecycle of the project
and do not reflect a consistent transcription convention, as is often the case when documenting a language.
For the parser to be able to process human annotations, it will need to be able to handle fuzzy matches.
For example the word /ùnɛ́ɾɛ́/ 'yesterday' can be found transcribed \[únːɛ̀ːɾɛ̀], \[ūnːɛ̄ːɾɛ̀], \[ùnɛ̀ré],
and the word /t̪òlé/ 'lion' can be found transcribed \[t̪òlí], \[t̪ʊ̀lɪ́], \[t̪ùlí] etc.
Ideally, fuzzy search should be able to account for the possible variation encountered in Tira transcriptions and enforce
a consistent standard.

## Methods
The Tira parser relies on FST technology with the Pynini python package as an interface.
Rules for morphological exponence for Tira are adapted from the analysis given in Hagen Kaldhol (2024).
Pynini provides functions for efficient creation of context-dependent rewrite rules
that are ideal for handling the complex patterns of exponence present in Tira.
In addition, the `pynini.lib.paradigms` module allows for easy creation and organization of
morphological paradigms including transducing inflected forms to glosses and vice versa.

## Dependencies
### Linux
Should just need `pip install -r requirements.txt`

### MacOS
Pynini requires [OpenFST 1.8.3](https://www.openfst.org/twiki/bin/view/FST/FstDownload). Earlier versions might work as well. If using 1.8.3 note the patch described in [this github issue](https://github.com/gpustack/gpustack/issues/1798#issuecomment-2980869111).

Once OpenFST is installed, `pip install -r requirements.txt` should work.

### Windows
Pynini is difficult to install on Windows, I suggest using WSL and following the Linux instructions.