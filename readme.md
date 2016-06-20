scovat: set coverage analysis tool
==================================

```usage: scovat.py (-gb BUILD | -i | -d | -u | -r) -o OUT IN [IN...]

Set Coverage Analysis Tool's (S.C.O.V.A.T) primary purpose is to transform,
analyze and report a provided set of coverage profiles with the gcov 'gcda'
file format by first generating an intermediate 'gcov' representation which
can be used to apply 'set union, intersection or difference' on n profiles.
Analyzing these results will give the code coverage metrics of the criteria
which are supplied by gcov (statement, branch and function), which can then
process the 'Hamming distance' and 'Jacard index', of two or more profiles.
Note: if two or more profiles are given for comparison, union will be used.
Interesting: scovat closely spells like one Romanian sweet pancake dessert.

positional arguments:
  IN                    list of testing profiles that are to be operated on.
                        Usually several test cases which are to be analyzed.
                        These *need* to match the path structure of 'BUILD',
                        at least when generating base intermediate profiles.

optional arguments:
  -h, --help            show this help message and exit
  -g, --generate        executes 'SCOVAT_GCOV' on all the profiles provided
                        with 'IN' and the reference 'BUILD' directory, such
                        that all '*.gcda' files use 'intermediate' formats.
                        Profiles stored in 'OUT', which can be operated on.
  -i, --intersection    applies the 'set intersection' operation on all the
                        'IN' profiles, producing the result profiles 'OUT'.
  -d, --difference      applies the 'left set difference' operation upon an
                        'IN' set of profiles, with 'IN[0]' as the left set.
                        Produces another profile 'OUT' with operation data.
  -u, --union           applies the simple 'set union' operation on all the
                        'IN' profiles given, then storing results in 'OUT'.
                        All operations transform the set criteria counters.
  -a, --analyze         produces the coverage report with statement, branch
                        and function criteria percentages of the 'union' of
                        all 'IN' profiles, with 'IN[0]' as the given anchor
                        which is used to, if '|IN| > 1' to also generate an
                        analysis, with the Hamming distance and the Jaccard
                        similarity coefficient between the anchor and rest.
                        Similarities use 'criteria hit' as the set element.
  -o OUT, --output OUT  generic 'OUTPUT' directory for resulting operation.
  -b DIR, --build DIR   matching 'BUILD' directory where profile was built.```
