#!/usr/bin/env python
#           scovat.py

import os
import sys
import time
import mmap
import shutil
import fnmatch
import argparse
import subprocess

class ScovatScript:
    GCOV = "gcov" # Location where the 'gcov -ib' can be found.
    USAGE = "(-gb BUILD | -i | -d | -u | -r) -o OUT IN [IN...]"
    DESCRIPTION = """
    Set Coverage Analysis Tool's (S.C.O.V.A.T) primary purpose is to transform,
    analyze and report a provided set of coverage profiles with the gcov 'gcda'
    file format by first generating an intermediate 'gcov' representation which
    can be used to apply 'set union, intersection or difference' on n profiles.
    Analyzing these results will give the code coverage metrics of the criteria
    which are supplied by gcov (statement, branch and function), which can then
    process the 'Hamming distance' and 'Jacard index', of two or more profiles.
    Note: if two or more profiles are given for comparison, union will be used.
    Interesting: scovat closely spells like one Romanian sweet pancake dessert.
    """

    def __init__(self):
        parser = argparse.ArgumentParser(description=self.DESCRIPTION,
                                         usage="%(prog)s "+self.USAGE)
        operation = parser.add_mutually_exclusive_group(required=True)
        operation = operation.add_argument
        option = parser.add_argument

        operation("-g", "--generate", dest="generate", action="store_true",
                  help="""executes 'SCOVAT_GCOV' on all the profiles provided
                          with 'IN' and the reference 'BUILD' directory, such
                          that all '*.gcda' files use 'intermediate' formats.
                          Profiles stored in 'OUT', which can be operated on.""")
        operation("-i", "--intersection", dest="intersection", action="store_true",
                  help="""applies the 'set intersection' operation on all the
                          'IN' profiles, producing the result profiles 'OUT'.""")
        operation("-d", "--difference", dest="difference", action="store_true",
                  help="""applies the 'left set difference' operation upon an
                          'IN' set of profiles, with 'IN[0]' as the left set.
                          Produces another profile 'OUT' with operation data.""")
        operation("-u", "--union", dest="union", action="store_true",
                  help="""applies the simple 'set union' operation on all the
                          'IN' profiles given, then storing results in 'OUT'.
                          All operations transform the set criteria counters.""")
        operation("-a", "--analyze", dest="analyze", action="store_true",
                  help="""produces the coverage report with statement, branch
                          and function criteria percentages of the 'union' of
                          all 'IN' profiles, with 'IN[0]' as the given anchor
                          which is used to, if '|IN| > 1' to also generate an
                          analysis, with the Hamming distance and the Jaccard
                          similarity coefficient between the anchor and rest.
                          Similarities use 'criteria hit' as the set element.""")

        option("-o", "--output", dest="output", metavar="OUT", required=True,
                help="""generic 'OUTPUT' directory for resulting operation.""")
        option("-b", "--build", dest="build", metavar="DIR",
               help="""matching 'BUILD' directory where profile was built.""")
        option("inputs", metavar="IN", nargs="+",
               help="""list of testing profiles that are to be operated on.
                       Usually several test cases which are to be analyzed.
                       These *need* to match the path structure of 'BUILD',
                       at least when generating base intermediate profiles.""")
        self.options = parser.parse_args()
        self.GCOV = os.getenv("SCOVAT_GCOV", self.GCOV)
        # Check that 'generate' always has 'build' and v.v.
        if self.options.generate and not self.options.build or\
           not self.options.generate and self.options.build:
            parser.print_help()
            sys.exit(1)

    def __enter__(self): return self
    def __exit__(self, etype, value, etrace): pass
    def execute(self, location=sys.argv[0]):
        begin = time.time()
        options = self.options
        # Only implicitly dependent argument is 'generate', it needs 'build' flag set.
        if options.generate: self.generate(options.build, options.output, options.inputs)
        elif options.intersection: self.transform(options.output, options.inputs, self.intersection)
        elif options.difference: self.transform(options.output, options.inputs, self.difference)
        elif options.union: self.transform(options.output, options.inputs, self.union)
        elif options.analyze: self.analyze(options.output, options.inputs)
        else: sys.exit(1) # Shouldn't really arrive here given argparse.
        print("executed in {0:.2f} seconds".format(time.time()-begin))

    def generate(self, build, output, inputs):
        devnull = open(os.devnull, 'w')
        for profile in inputs:
            self.print_crawl(profile)
            command = "find '{}' -name '*.gcda'".format(profile)
            # Crawl the input directory and try to find all of the GCDA files.
            results = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (outputs, errors) = results.communicate() # Extract stdout and stderr data.
            files = outputs.decode().split() # Split continuous file output to list.
            relative_files = [os.path.relpath(f, start=profile) for f in files]

            build_files = []
            self.print_copy(profile, build)
            for i in xrange(len(files)):
                # Determine location of the raw binary coverages.
                build_file = os.path.join(build, relative_files[i])
                # Copy data files to correct location in build dir.
                shutil.copy(files[i], build_file)
                build_files.append(build_file)

            # Determine correct relative location in output path.
            normal_path = os.path.basename(os.path.normpath(profile))
            output_path = os.path.join(output, normal_path)
            self.print_process(build, output_path)
            if not os.path.isdir(output_path):
                os.makedirs(output_path)

            # Generate intermediate files.
            for build_file in build_files:
                # Change directory to output, since gcov outputs there.
                command = "{} -ib '{}'".format(self.GCOV, os.path.abspath(build_file))
                if subprocess.call(command, shell=True, cwd=output_path,
                                   stdout=devnull, stderr=subprocess.STDOUT) == 1:
                    print("Need to have 'gcov' path defined in SCOVAT_GCOV env!")
                    sys.exit(1) # Nothing can be done about this, just terminate.

    def analyze(self, output, inputs):
        profiles = inputs ; profile_anchor = profiles[0]
        if len(profiles) != 1: self.transform(output, profiles[1:], self.union)
        else: shutil.rmtree(output, ignore_errors=True)
        # After this, only two profiles, A and B exists. Only if several files.
        # Where B is 'union' of them, except the anchor. Anchor isn't analyzed.
        if not os.path.exists(output):
            os.makedirs(output)

        # Find out matching and unmatching files here.
        anchor_files = set(os.listdir(profile_anchor))
        output_files = set(os.listdir(output))
        matched = output_files & anchor_files
        runmatched = output_files - anchor_files
        lunmatched = anchor_files - output_files

        for luprofile in lunmatched:
            output_path = os.path.join(output, luprofile)
            anchor_path = os.path.join(profile_anchor, luprofile)
            self.print_report(anchor_path, output_path)
            anchor_transform = self.Transform()
            anchor_transform.read(anchor_path)
            analysis = self.Analysis()
            analysis.process(anchor_transform, 0)
            analysis.write(output_path)

        for ruprofile in runmatched:
            output_path = os.path.join(output, ruprofile)
            self.print_report(output_path, output_path)
            output_transform = self.Transform()
            output_transform.read(output_path)
            analysis = self.Analysis()
            analysis.process(output_transform, 1)
            analysis.write(output_path)

        for mprofile in matched:
            output_path = os.path.join(output, mprofile)
            anchor_path = os.path.join(profile_anchor, mprofile)
            self.print_compare(anchor_path, output_path, output_path)
            (a, b) = (output_path, anchor_path)
            (at, bt) = (self.Transform(), self.Transform())
            at.read(a) ; bt.read(b) # Parse profile data.
            analysis = self.Analysis() # Results from it.
            analysis.compare(at, bt) # Hamming, Jaccard.
            analysis.write(output_path) # Overwrite tmp.

        print("==============ANALYSIS==============")
        if analysis.functions[1] > 0:
            print("function coverage ratio: {:.2f}%".format(float(analysis.functions[0]) / float(analysis.functions[1]) * 100))
            if analysis.jaccard[0][1] > 0:
                jaccard = float(analysis.jaccard[0][0]) / float(analysis.jaccard[0][1])
                print("function jaccard coefficient: {:.2f}".format(jaccard))
            print("function hamming distance: {}".format(analysis.hamming[0]))
        if analysis.branches[1] > 0:
            print("branch coverage: {:.2f}%".format(float(analysis.branches[0]) / float(analysis.branches[1]) * 100))
            if analysis.jaccard[1][1] > 0:
                jaccard = float(analysis.jaccard[1][0]) / float(analysis.jaccard[1][1])
                print("branch jaccard coefficient: {:.2f}".format(jaccard))
            print("branch hamming distance: {}".format(analysis.hamming[1]))
        if analysis.statements[1] > 0:
            print("statement coverage: {:.2f}%".format(float(analysis.statements[0]) / float(analysis.statements[1]) * 100))
            if analysis.jaccard[2][1] > 0:
                jaccard = float(analysis.jaccard[2][0]) / float(analysis.jaccard[2][1])
                print("statement jaccard coefficient: {:.2f}".format(jaccard))
            print("statement hamming distance: {}".format(analysis.hamming[2]))

    def transform(self, output, inputs, operation):
        profiles = inputs
        result = profiles[0]
        devnull = open(os.devnull, 'w')
        result_files = os.listdir(result)
        self.print_copy(result, output)
        if not os.path.exists(output):
            os.makedirs(output)
        # Copy first profile to the output directory.
        [shutil.copy(os.path.join(result, f), output)
                     for f in result_files]
        del profiles[0] # Already processed.

        for profile in profiles:
            # Find the sets of (un)matched files.
            profile_files = set(os.listdir(profile))
            runmatched = profile_files - set(result_files)
            lunmatched = set(result_files) - profile_files
            matched = profile_files & set(result_files)

            # Right unmatched profiles.
            for ruprofile in runmatched:
                output_path = os.path.join(output, ruprofile)
                ruprofile_path = os.path.join(profile, ruprofile)
                self.print_copy(ruprofile_path, output)
                shutil.copy(ruprofile_path, output)
                if operation == self.difference or\
                   operation == self.intersection:
                    self.print_process(output_path, output_path)
                    ruprofile_transform = self.Transform()
                    ruprofile_transform.read(output_path)
                    ruprofile_transform.identity() # Zero.
                    ruprofile_transform.write(output_path)
            result_files.extend(runmatched)

            # Left unmatched profiles.
            for luprofile in lunmatched:
                output_path = os.path.join(output, luprofile)
                luprofile_path = os.path.join(profile, luprofile)
                if  operation == self.intersection:
                    self.print_process(output_path, output_path)
                    luprofile_transform = self.Transform()
                    luprofile_transform.read(output_path)
                    luprofile_transform.identity() # Zero.
                    luprofile_transform.write(output_path)

            # Matched set of files.
            for mprofile in matched:
                output_path = os.path.join(output, mprofile)
                profile_path = os.path.join(profile, mprofile)
                self.print_process(profile_path, output_path)
                (a, b) = (output_path, profile_path)
                (at, bt) = (self.Transform(), self.Transform())
                at.read(a) ; bt.read(b) # Parse profile data.
                operation(at, bt) # Apply operations on them.
                at.write(a) # Overwrite profile data on disk.

    def intersection(self, aprof, bprof):
        def function(a, b):
            if a.count == 0 or\
               b.count == 0:
                a.count = 0
            else: a.count += b.count
        def branch(a, b):
            if a.btype == "taken" and\
               b.btype == "taken":
                a.btype = "taken"
            elif (a.btype == "taken" and\
                  b.btype == "nottaken") or\
                 (a.btype == "nottaken" and\
                  b.btype == "taken") or\
                 (a.btype == "nottaken" and \
                  b.btype == "nottaken"):
                  a.btype = "nottaken"
            else: a.btype = "notexec"
        def statement(a, b):
            if a.count == 0 or\
               b.count == 0:
                a.count = 0
            else: a.count += b.count

        for name in aprof.files:
            afile = aprof.files[name]
            if name in bprof.files:
                bfile = bprof.files[name]
                for f in xrange(len(afile.functions)):
                    function(afile.functions[f],
                             bfile.functions[f])
                for b in xrange(len(afile.branches)):
                    branch(afile.branches[b],
                           bfile.branches[b])
                for s in xrange(len(afile.statements)):
                    statement(afile.statements[s],
                              bfile.statements[s])
            else: aprof.file_identity(name)
        for name in bprof.files:
            if name not in aprof.files:
                aprof.files[name] = bprof.files[name]
                aprof.file_identity(name)

    def difference(self, aprof, bprof):
        def function(a, b):
            if b.count != 0:
                a.count = 0
        def branch(a, b):
            if a.btype == b.btype:
                a.btype = "notexec"
        def statement(a, b):
            if b.count != 0:
                a.count = 0

        for name in aprof.files:
            afile = aprof.files[name]
            if name in bprof.files:
                bfile = bprof.files[name]
                for f in xrange(len(afile.functions)):
                    function(afile.functions[f],
                             bfile.functions[f])
                for b in xrange(len(afile.branches)):
                    branch(afile.branches[b],
                           bfile.branches[b])
                for s in xrange(len(afile.statements)):
                    statement(afile.statements[s],
                              bfile.statements[s])
        for name in bprof.files:
            if name not in aprof.files:
                aprof.files[name] = bprof.files[name]
                aprof.file_identity(name)

    def union(self, aprof, bprof):
        def function(a, b):
            a.count += b.count
        def branch(a, b):
            if a.btype == "taken" or\
               b.btype == "taken":
                a.btype = "taken"
            elif a.btype == "nottaken" or\
                 b.btype == "nottaken":
                a.btype = "nottaken"
        def statement(a, b):
            a.count += b.count

        for name in aprof.files:
            afile = aprof.files[name]
            if name in bprof.files:
                bfile = bprof.files[name]
                for f in xrange(len(afile.functions)):
                    function(afile.functions[f],
                             bfile.functions[f])
                for b in xrange(len(afile.branches)):
                    branch(afile.branches[b],
                           bfile.branches[b])
                for s in xrange(len(afile.statements)):
                    statement(afile.statements[s],
                              bfile.statements[s])
        for name in bprof.files:
            if name not in aprof.files:
                aprof.files[name] = bprof.files[name]

    class Transform:
        class Statement:
            def __init__(self, line, count):
                self.count = count
                self.line = line
        class Branch:
            def __init__(self, line, btype):
                self.btype = btype
                self.line = line
        class Function:
            def __init__(self, line, count, name):
                self.count = count
                self.line = line
                self.name = name
        class File:
            def __init__(self, name):
                self.branches = []
                self.statements = []
                self.functions = []
                self.name = name
        def __init__(self):
            self.files = {}

        def read(self, path):
            with open(path, "r+b") as handle:
                # Map all file contents into memory.
                data = mmap.mmap(handle.fileno(), 0,
                                prot=mmap.PROT_READ)
                # Parse intermediate representation.
                self.parse(data) # Optimize looping?
                handle.close() # Data already here.
        def write(self, path):
            with open(path, "w") as handle:
                for name in self.files:
                    profile = self.files[name]
                    handle.write("file:{}\n".format(profile.name))
                    for f in profile.functions: handle.write("function:{},{},{}\n".format(f.line, f.count, f.name))
                    for b in profile.branches: handle.write("branch:{},{}\n".format(b.line, b.btype))
                    for s in profile.statements: handle.write("lcount:{},{}\n".format(s.line, s.count))
        def file_identity(self, name):
            for f in self.files[name].functions: f.count = 0
            for b in self.files[name].branches: b.btype = "notexec"
            for s in self.files[name].statements: s.count = 0
        def identity(self):
            for name in self.files:
                for f in self.files[name].functions: f.count = 0
                for b in self.files[name].branches: b.btype = "notexec"
                for s in self.files[name].statements: s.count = 0
        def parse(self, data):
            for line in iter(data.readline, ""):
                contents = line.split(":")
                content = contents[1].rstrip("\r\n")
                token = contents[0]
                if token == "file":
                    self.files[content] = self.File(content)
                    current_file = self.files[content] # Optimize this later?
                else: # Strip according to the common delimiter, then handle token.
                    content = content.split(",") # Might want to handle the case when arguments don't match a certain int type cast?
                    if token == "lcount": current_file.statements.append(self.Statement(int(content[0]), int(content[1])))
                    elif token == "branch": current_file.branches.append(self.Branch(int(content[0]), content[1]))
                    elif token == "function": current_file.functions.append(self.Function(int(content[0]), int(content[1]), content[2]))

    class Analysis:
        class File:
            def __init__(self, name):
                self.name = name
                self.branches = [0, 0]
                self.statements = [0, 0]
                self.functions = [0, 0]
                self.hamming = [0, 0, 0]
                self.jaccard = [0, 0, 0]
        branches = [0, 0] # (branches hit, total branches)
        statements = [0, 0] # (statements hit, total statements)
        functions = [0, 0] # (functions hit, total functions)
        hamming = [0, 0, 0] # (function, branch, statement)
        jaccard = [[0, 0], # (function, branch, statement)
                   [0, 0], # then for each, the following:
                   [0, 0]] # (intersected hits, union hit)
        def __init__(self):
            self.files = {}

        def process(self, transform, side):
            for name in transform.files:
                profile = transform.files[name]
                self.files[name] = self.File(name)
                p = self.files[name] # For easy access.

                p.functions[1] = len(profile.functions)
                for f in profile.functions:
                    if f.count > 0:
                        p.functions[0] += 1
                p.hamming[0] = p.functions[0]
                p.branches[1] = len(profile.branches)
                for b in profile.branches:
                    if b.btype == "taken":
                        p.branches[0] += 1
                p.hamming[1] = p.branches[0]
                p.statements[1] = len(profile.statements)
                for s in profile.statements:
                    if s.count > 0:
                        p.statements[0] += 1
                p.hamming[2] = p.statements[0]
                p.jaccard = [0.0, 0.0, 0.0]

                self.jaccard[0][side] += p.functions[0]
                self.jaccard[1][side] += p.branches[0]
                self.jaccard[2][side] += p.statements[0]
                self.functions[1] += len(profile.functions)
                self.functions[0] += p.functions[0]
                self.branches[1] += len(profile.branches)
                self.branches[0] += p.branches[0]
                self.statements[1] += len(profile.statements)
                self.statements[0] += p.statements[0]
                self.hamming[0] += p.hamming[0]
                self.hamming[1] += p.hamming[1]
                self.hamming[2] += p.hamming[2]

        def compare(self, af, bf):
            for name in af.files:
                aprofile = af.files[name]
                if name in bf.files:
                    bprofile = bf.files[name]
                    self.files[name] = self.File(name)
                    p = self.files[name] # Easy access.

                    jaccard_hits = 0
                    p.functions[1] = len(aprofile.functions)
                    for f in xrange(len(aprofile.functions)):
                        ahit = aprofile.functions[f].count > 0
                        bhit = bprofile.functions[f].count > 0
                        if ahit and bhit: jaccard_hits += 1
                        if ahit or bhit: p.functions[0] += 1
                        if ahit != bhit: p.hamming[0] += 1
                    if p.functions[0] > 0:
                        p.jaccard[0] = float(jaccard_hits) / float(p.functions[0])
                        self.jaccard[0][1] += p.functions[0]
                        self.jaccard[0][0] += jaccard_hits

                    jaccard_hits = 0
                    p.branches[1] = len(aprofile.branches)
                    for b in xrange(len(aprofile.branches)):
                        ahit = aprofile.branches[b].btype == "taken"
                        bhit = bprofile.branches[b].btype == "taken"
                        if ahit and bhit: jaccard_hits += 1
                        if ahit or bhit: p.branches[0] += 1
                        if ahit != bhit: p.hamming[1] += 1
                    if p.branches[0] > 0:
                        p.jaccard[1] = float(jaccard_hits) / float(p.branches[0])
                        self.jaccard[1][1] += p.branches[0]
                        self.jaccard[1][0] += jaccard_hits

                    jaccard_hits = 0 # New trendy summer hits!
                    p.statements[1] = len(aprofile.statements)
                    for s in xrange(len(aprofile.statements)):
                        ahit = aprofile.statements[s].count > 0
                        bhit = bprofile.statements[s].count > 0
                        if ahit and bhit: jaccard_hits += 1
                        if ahit or bhit: p.statements[0] += 1
                        if ahit != bhit: p.hamming[2] += 1
                    if p.statements[0] > 0:
                        p.jaccard[2] = float(jaccard_hits) / float(p.statements[0])
                        self.jaccard[2][1] += p.statements[0]
                        self.jaccard[2][0] += jaccard_hits

                    self.functions[1] += len(aprofile.functions)
                    self.functions[0] += p.functions[0]
                    self.branches[1] += len(aprofile.branches)
                    self.branches[0] += p.branches[0]
                    self.statements[1] += len(aprofile.statements)
                    self.statements[0] += p.statements[0]
                    self.hamming[0] += p.hamming[0]
                    self.hamming[1] += p.hamming[1]
                    self.hamming[2] += p.hamming[2]
                else: print("UNMATCHED PROFILE OK?")

        def write(self, path):
            with open(path, "w") as handle:
                for name in self.files:
                    profile = self.files[name]
                    handle.write("analysis:{}\n".format(profile.name))
                    if profile.functions[1] > 0: handle.write("functions:{},{},{:.2f}%\n".format(profile.functions[0], profile.functions[1],
                                                              float(profile.functions[0]) / float(profile.functions[1]) * 100))
                    if profile.branches[1] > 0: handle.write("branches:{},{},{:.2f}%\n".format(profile.branches[0], profile.branches[1],
                                                             float(profile.branches[0]) / float(profile.branches[1]) * 100))
                    if profile.statements[1] > 0: handle.write("statements:{},{},{:.2f}%\n".format(profile.statements[0], profile.statements[1],
                                                               float(profile.statements[0]) / float(profile.statements[1]) * 100))
                    handle.write("jaccard:{:.2f},{:.2f},{:.2f}\n".format(profile.jaccard[0], profile.jaccard[1], profile.jaccard[2]))
                    handle.write("hamming:{},{},{}\n".format(profile.hamming[0], profile.hamming[1], profile.hamming[2]))

    def print_crawl(self, folder):
        print("crawling   '{}'".format(folder))
    def print_copy(self, origin, destination):
        print("copying    '{}' to '{}'".format(origin, destination))
    def print_process(self, folder, output):
        print("processing '{}' to '{}'".format(folder, output))
    def print_compare(self, aprofile, bprofile, path):
        print("comparing  '{}' and '{}' to '{}'".format(aprofile, bprofile, path))
    def print_report(self, path, output):
        print("reporting  '{}' to '{}'".format(path, output))

INIT_ERROR_STATE = -1
if __name__ == "__main__":
    status = INIT_ERROR_STATE
    with ScovatScript() as tool:
        status = tool.execute()
    sys.exit(status)
