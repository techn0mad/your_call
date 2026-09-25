# Callsign Ranker

`your_call.py` ranks amateur-radio callsigns using a combination
of CW efficiency, CW copyability, voice/phonetic efficiency, and
callsign distinctiveness.

The goal is not simply to find the callsign containing the fewest dots
and dashes. A good callsign should also be easy to send, easy to
recognize under marginal conditions, easy to communicate phonetically,
and resistant to common copying errors.

The program assigns each callsign an overall **goodness score from 0
to 100** and can also display the individual component scores used to
produce that result.

## Requirements

The program requires Python 3 and uses only modules from the Python
standard library.

No additional packages are required.

## Input

The input is a plain-text file containing one callsign per line:

```text
VE7HTE
VE7IMT
VE7TUE
VE7ESI
VA7EIE
```

Blank lines are ignored and callsigns are converted to uppercase.

The current parser expects callsigns consisting of:

- an alphabetic prefix;
- a digit; and
- an alphabetic suffix.

For example:

```text
VE7HTE
VA7EIE
VE7OL
```

The first digit terminates the prefix, so:

```text
VE7HTE
```

is interpreted as:

```text
prefix = VE7
suffix = HTE
```

## Basic Usage

Rank all callsigns in a file:

```console
$ python3 your_call.py bc_calls.txt
```

By default, the top 25 results are displayed.

Change the number of results with `-n` or `--number`:

```console
$ python3 your_call.py bc_calls.txt -n 50
```

Restrict the analysis to a particular prefix:

```console
$ python3 your_call.py bc_calls.txt --prefix VE7
```

For example:

```console
$ python3 your_call.py bc_calls.txt --prefix VE7 -n 25
```

displays the 25 highest-ranked VE7 callsigns in the input file.

## Detailed Scoring

The `--detail` option displays the individual measurements and
component scores for a callsign:

```console
$ python3 your_call.py bc_calls.txt --prefix VE7 --detail VE7HTE
```

This is useful for understanding why one callsign ranks above another.

## Scoring Philosophy

The scoring system considers several properties of a callsign.

The current weights are:

| Criterion | Weight |
| --- | ---: |
| Suffix length | 20% |
| CW transmission time | 15% |
| CW element count | 10% |
| CW boundary contrast | 10% |
| CW boundary-run resistance | 5% |
| CW rhythm | 10% |
| Phonetic length | 10% |
| Phonetic contrast | 8% |
| Prefix/suffix uniqueness | 7% |
| Adjacent duplicate avoidance | 3% |
| Memorability | 2% |
| **Total** | **100%** |

These weights are intentionally kept in the `WEIGHTS` dictionary near
the beginning of the program so that they can easily be adjusted.

## CW Metrics

### Suffix Length

Short suffixes are generally desirable.

For example:

```text
VE7OL
```

has an inherent advantage over:

```text
VE7HTE
```

because only two suffix characters need to be sent, copied,
remembered, typed, or repeated.

### Morse Element Count

Each dot or dash is counted as one Morse element.

For example:

```text
HTE = .... - .
```

contains:

```text
4 + 1 + 1 = 6 elements
```

while:

```text
IMT = .. -- -
```

contains:

```text
2 + 2 + 1 = 5 elements
```

Fewer elements generally means less keying effort.

### CW Transmission Time

Element count alone does not accurately represent transmission time
because a dash takes three times as long as a dot.

Standard Morse timing is used:

```text
dot                 1 unit
dash                3 units
intra-element gap   1 unit
inter-character gap 3 units
```

Consequently, a callsign with fewer elements is not necessarily faster
than one with more elements.

The program therefore measures both **element count** and **elapsed CW time**.

## CW Boundary Contrast

Character boundaries can become difficult to recognize when the last
Morse element of one character is the same as the first element of the
next.

Consider:

```text
HTE = .... | - | .
```

At both boundaries the element changes:

```text
dot  -> dash
dash -> dot
```

This gives `HTE` a boundary-contrast score of 100%.

Compare this with:

```text
IMT = .. | -- | -
```

The first boundary changes from dot to dash, but the second is:

```text
dash -> dash
```

so `IMT` receives a 50% boundary-contrast score.

An extreme example is:

```text
ESI = . | ... | ..
```

All of the elements are dots. The distinction between the three
characters depends entirely on recognizing the longer inter-character
gaps.

Its boundary-contrast score is therefore 0%.

The intent of this metric is to reward suffixes whose individual
characters remain acoustically distinct.

## CW Boundary Runs

The program also detects runs of identical elements that cross
character boundaries.

For example:

```text
MT = -- | -
```

places three dashes adjacent to one another. The listener must
recognize the longer inter-character gap to distinguish `M T` from a
continuous sequence of dashes.

Longer cross-boundary runs receive a larger penalty.

By contrast:

```text
HT = .... | -
```

changes from dots to a dash at the character boundary and receives no
boundary-run penalty.

This metric complements the boundary-contrast score by considering the
severity of a potentially ambiguous boundary.

## CW Rhythm

The program contains a preliminary CW rhythm heuristic.

It compares the Morse structures of adjacent characters and rewards
suffixes whose characters have substantially different patterns.

For example:

```text
HTE = .... / - / .
```

has a very distinctive rhythm because its three characters have
substantially different Morse forms.

The current implementation should be considered a first approximation
rather than a formal model of human CW perception.

A future version could replace this heuristic with a Morse-specific
edit-distance or confusability model.

## Phonetic Metrics

The program uses the ICAO/NATO phonetic alphabet.

For example:

```text
VE7OL
```

has the suffix:

```text
Oscar Lima
```

while:

```text
VE7IMT
```

has:

```text
India Mike Tango
```

### Phonetic Length

The approximate number of spoken syllables is calculated for each suffix.

For example:

```text
Golf       1
Mike       1
Echo       2
Lima       2
India      3
Uniform    3
```

Lower syllable counts are preferred.

### Phonetic Contrast

Repeated suffix characters reduce phonetic distinctiveness.

For example:

```text
UEE = Uniform Echo Echo
```

contains a repeated phonetic word, while:

```text
HTE = Hotel Tango Echo
```

contains three different phonetic words.

The current phonetic-contrast metric is intentionally simple. It
measures character uniqueness rather than attempting to model the
acoustic similarity of spoken phonetic words.

## Prefix/Suffix Uniqueness

Suffix characters that do not occur in the prefix are preferred.

For example:

```text
VE7OL
```

contains five different callsign characters:

```text
V E 7 O L
```

whereas:

```text
VE7LV
```

repeats `V`:

```text
V E 7 L V
```

This is a relatively small component of the score, but unique
characters can improve memorability and reduce ambiguity.

## Adjacent Duplicate Characters

Adjacent duplicate suffix characters receive a penalty.

For example:

```text
UEE
```

contains adjacent `E` characters.

On CW:

```text
..- | . | .
```

the repeated characters depend strongly on correct recognition of
character spacing.

On voice:

```text
Uniform Echo Echo
```

one occurrence of `Echo` could potentially be missed.

A suffix such as:

```text
HTE
```

has no adjacent duplicates.

## Memorability

A small portion of the score is reserved for simple memorability
characteristics.

The current implementation rewards:

- character uniqueness; and
- simple suffix symmetry.

Because memorability and aesthetics are inherently subjective, this
component deliberately has very little influence on the overall score.

## Interpreting Scores

The overall score is intended primarily as a **ranking and comparison
tool**, not as an absolute statement that one callsign is objectively
better than another.

For example, two calls might make different tradeoffs:

```text
VE7OL
VE7LV
```

`OL` has fewer Morse elements, no character duplicated from the
prefix, and strong CW boundary contrast:

```text
--- | .-..
```

`LV` has a slightly shorter elapsed CW transmission time:

```text
.-.. | ...-
```

The scoring model combines these properties rather than relying on a
single measurement.

Similarly:

```text
HTE = .... / - / .
IMT = ..   / -- / -
```

`IMT` uses fewer Morse elements, while `HTE` has stronger
character-boundary contrast.

The purpose of the score is to make such tradeoffs explicit and reproducible.

## Population-Relative Scores

Some metrics in the current implementation are normalized against the
callsigns present in the input file.

This works well for ranking a particular availability list, but it
means an overall score may change if the candidate population changes.

For example, a callsign scoring 87 in one candidate file might not
receive exactly 87 when analyzed against a substantially different
candidate set.

A future version should use fixed normalization scales so that a score
has the same meaning regardless of the candidate list.

This would make scores directly comparable between different
availability lists and between manually supplied candidates.

## Design Principle

The overall philosophy behind the program is:

> A good callsign should be short enough to send efficiently, but
> distinctive enough that it does not need to be sent twice.

Raw CW speed is therefore only one consideration.

A slightly longer callsign may be preferable if its Morse rhythm,
character boundaries, phonetics, and overall distinctiveness make it
substantially easier to copy correctly under real-world conditions.

## Limitations

The scoring system is experimental.

In particular:

- CW rhythm is represented by a heuristic rather than measured human
  copyability.
- Phonetic contrast does not yet model acoustic similarity between
  NATO phonetic words.
- Memorability is necessarily subjective.
- Operator skill, sending style, speed, fading, QRM, QRN, and
  propagation can affect real-world copyability.
- The weighting of criteria reflects design choices rather than
  established amateur-radio standards.

The component scores are exposed specifically so these assumptions can
be examined and adjusted.

## Possible Future Improvements

Potential improvements include:

- fixed rather than population-relative scoring scales;
- a Morse edit-distance/confusability model;
- modeling insertion or deletion of dots and dashes;
- modeling missed or shortened character spaces;
- measuring maximum identical-element runs across character boundaries;
- improved acoustic-distance scoring for NATO phonetic words;
- configurable scoring weights;
- CSV or JSON output;
- comparison of explicitly supplied callsigns;
- generation and ranking of all possible suffixes;
- separate CW, voice, and combined rankings.

## License

ISC License
