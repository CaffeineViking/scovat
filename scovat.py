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
    """

    def __init__(self):
        parser = argparse.ArgumentParser(description=self.DESCRIPTION,
                                         usage="%(prog)s "+self.USAGE)
        operation = parser.add_mutually_exclusive_group(required=True)
        operation = operation.add_argument
        option = parser.add_argument

        operation("-g", "--generate", dest="generate", action="store_true",
                  help="""""")
        operation("-i", "--intersection", dest="intersection", action="store_true",
                  help="""""")
        operation("-d", "--difference", dest="difference", action="store_true",
                  help="""""")
        operation("-u", "--union", dest="union", action="store_true",
                  help="""""")
        operation("-r", "--report", dest="report", action="store_true",
                  help="""""")

        option("-o", "--output", dest="output", metavar="OUT", required=True,
                help="""""")
        option("-b", "--build", dest="build", metavar="DIR",
               help="""""")
        option("inputs", metavar="IN", nargs="+",
               help="""""")
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
        elif options.report: self.analyze(options.output, options.inputs)
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

    def analyze(self, output, inputs): pass
    def transform(self, output, inputs, operation):
        profiles = inputs
        result = profiles[0]
        devnull = open(os.devnull, 'w')
        result_files = os.listdir(result)
        self.print_copy(result, output)

        if not os.path.exists(output):
            os.makedirs(output)
        # Copy first profile to output directory.
        [shutil.copy(os.path.join(result, f), output)
                     for f in result_files]
        del profiles[0] # Already processed.

        for profile in profiles:
            # Find the sets of (un)matched files.
            profile_files = set(os.listdir(profile))
            unmatched = profile_files - set(result_files)
            matched = profile_files & set(result_files)

            # Just copy unmatched.
            for uprofile in unmatched:
                uprofile_path = os.path.join(profile, uprofile)
                self.print_copy(uprofile_path, output)
                shutil.copy(uprofile_path, output)
            result_files.extend(unmatched)

            # Process any matched.
            for mprofile in matched:
                output_path = os.path.join(output, mprofile)
                profile_path = os.path.join(profile, mprofile)
                self.print_process(profile_path, output_path)
                (a, b) = (output_path, profile_path)
                with open(a, "r+b") as afile,\
                     open(b, "r+b") as bfile:
                    # Map all file contents into memory.
                    adata = mmap.mmap(afile.fileno(), 0,
                                    prot=mmap.PROT_READ)
                    bdata = mmap.mmap(bfile.fileno(), 0,
                                    prot=mmap.PROT_READ)
                    # Parse intermediate representations.
                    aparsed = self.parse_transform(adata)
                    bparsed = self.parse_transform(bdata)
                    # Don't need these anymore, yay!
                    bdata.close() ; adata.close()
                    operation(aparsed, bparsed) # Go!
                    # Results overwrite the 'a' profile.
                    self.write_transform(aparsed, a)

    def intersection(self, aprof, bprof):
        for name in aprof.files:
            afile = aprof.files[name]
            if name in bprof.files:
                bfile = bprof.files[name]
                for f in xrange(len(afile.functions)):
                    if afile.functions[f].count == 0 or\
                       bfile.functions[f].count == 0:
                        afile.functions[f].count = 0
                    else: afile.functions[f].count += bfile.functions[f].count
                for b in xrange(len(afile.branches)):
                    if bfile.branches[b].btype == "taken" and\
                       afile.branches[b].btype == "taken":
                        afile.branches[b].btype = "taken"
                    elif (bfile.branches[b].btype == "nottaken" and\
                         afile.branches[b].btype == "taken") or\
                         (bfile.branches[b].btype == "taken" and\
                         afile.branches[b].btype == "nottaken") or\
                         (bfile.branches[b].btype == "nottaken" and\
                         afile.branches[b].btype == "nottaken"):
                        afile.branches[b].btype = "nottaken"
                    else: afile.branches[b].btype = "notexec"
                for s in xrange(len(afile.statements)):
                    if afile.statements[s].count == 0 or\
                       bfile.statements[s].count == 0:
                        afile.statements[s].count = 0
                    else: afile.statements[s].count += bfile.statements[s].count
        for name in bprof.files:
            if name not in aprof.files:
                aprof.files[name] = bprof.files[name]
                for f in aprof.files[name].functions:
                    f.count = 0
                for b in aprof.files[name].branches:
                    b.btype = "notexec"
                for s in aprof.files[name].statements:
                    s.count = 0

    def difference(self, aprof, bprof):
        for name in aprof.files:
            afile = aprof.files[name]
            if name in bprof.files:
                bfile = bprof.files[name]
                for f in xrange(len(afile.functions)):
                    if bfile.functions[f].count != 0:
                        afile.functions[f].count = 0
                for b in xrange(len(afile.branches)):
                    if bfile.branches[b].btype == afile.branches[b].btype:
                        afile.branches[b].btype = "notexec"
                for s in xrange(len(afile.statements)):
                    if bfile.statements[s].count != 0:
                        afile.statements[s].count = 0
        for name in bprof.files:
            if name not in aprof.files:
                aprof.files[name] = bprof.files[name]
                for f in aprof.files[name].functions:
                    f.count = 0
                for b in aprof.files[name].branches:
                    b.btype = "notexec"
                for s in aprof.files[name].statements:
                    s.count = 0

    def union(self, aprof, bprof):
        for name in aprof.files:
            afile = aprof.files[name]
            if name in bprof.files:
                bfile = bprof.files[name]
                for f in xrange(len(afile.functions)):
                    afile.functions[f].count += bfile.functions[f].count
                for b in xrange(len(afile.branches)):
                    if bfile.branches[b].btype == "taken":
                        afile.branches[b].btype = "taken"
                    elif bfile.branches[b].btype == "nottaken" and\
                         afile.branches[b].btype == "notexec":
                        afile.branches[b].btype = "nottaken"
                for s in xrange(len(afile.statements)):
                    afile.statements[s].count += bfile.statements[s].count
        for name in bprof.files:
            if name not in aprof.files:
                aprof.files[name] = bprof.files[name]

    def report(self, aprof, bprof): pass
    def hamming(self, aprof, bprof): pass
    def jaccard(self, aprof, bprof): pass

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

    def write_transform(self, data, output):
        with open(output, "w") as profile:
            for i in data.files:
                p = data.files[i]
                profile.write("file:{}\n".format(p.name))
                for f in p.functions: profile.write("function:{},{},{}\n".format(f.line, f.count, f.name))
                for b in p.branches: profile.write("branch:{},{}\n".format(b.line, b.btype))
                for s in p.statements: profile.write("lcount:{},{}\n".format(s.line, s.count))

    def parse_transform(self, data):
        result = self.Transform()
        for line in iter(data.readline, ""):
            contents = line.split(":")
            content = contents[1].rstrip("\r\n")
            token = contents[0]
            if token == "file":
                result.files[content] = self.Transform.File(content)
                current_file = result.files[content] # Optimize this later?
            else: # Strip according to the common delimiter, then handle token.
                content = content.split(",") # Might want to handle the case when arguments don't match a certain int type cast?
                if token == "lcount": current_file.statements.append(self.Transform.Statement(int(content[0]), int(content[1])))
                elif token == "branch": current_file.branches.append(self.Transform.Branch(int(content[0]), content[1]))
                elif token == "function": current_file.functions.append(self.Transform.Function(int(content[0]), int(content[1]), content[2]))
        return result

    class Analysis:
        class File:
            def __init__(self, name):
                self.name = name
                self.branches = 0
                self.total_branches = 0
                self.branch_distance = 0
                self.statements = 0
                self.total_statements = 0
                self.statement_distance = 0
                self.functions = 0
                self.total_function = 0
                self.function_distance = 0
        def __init__(self):
            self.files = {}

    def write_analysis(self, data, output):
        with open(output, "w") as profile:
            for i in data.files:
                p = data.files[i]
                profile.write("file:{}\n".format(p.name))
                profile.write("functions:{},{},{0:.2f}\n".format(p.functions,
                                                                 p.total_functions,
                                                                 p.functions / p.total_functions))
                profile.write("branches:{},{},{0:.2f}\n".format(p.branches,
                                                                p.total_branches,
                                                                p.branches / p.total_branches))
                profile.write("statements:{},{},{0:.2f}\n".format(p.statements,
                                                                  p.total_statements,
                                                                  p.statements / p.total_statements))
                profile.write("hamming:{},{},{}\n".format(42, 42, 42))
                profile.write("jaccard:{},{},{}\n".format(42, 42, 42))

    def parse_analysis(self, data): pass

    def print_crawl(self, folder):
        print("crawling '{}'".format(folder))
    def print_copy(self, origin, destination):
        print("copying '{}' to '{}'".format(origin, destination))
    def print_remove(self, path):
        print("removing '{}'".format(path))
    def print_process(self, folder, output):
        print("processing '{}' to '{}'".format(folder, output))

INIT_ERROR_STATE = -1
if __name__ == "__main__":
    status = INIT_ERROR_STATE
    with ScovatScript() as tool:
        status = tool.execute()
    sys.exit(status)
