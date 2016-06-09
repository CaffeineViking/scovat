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
        for input in inputs:
            command = "find "
            command += "'" + input +  "' "
            command += "-name '*.gcda'"
            self.print_crawl(input)

            # Crawl the input directory and try to find all of the GCDA files.
            results = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (outputs, errors) = results.communicate() # Extract stdout and stderr data.
            files = outputs.decode().split() # Split continuous file output to list.
            relative_files = [os.path.relpath(file, start=input) for file in files]

            build_files = []
            self.print_copy(input, build)
            for i in range(len(files)):
                # Determine location of the raw binary coverages.
                build_file = os.path.join(build, relative_files[i])
                # Copy data files to correct location in build dir.
                shutil.copy(files[i], build_file)
                build_files.append(build_file)

            # Determine correct relative location in output path.
            normal_path = os.path.basename(os.path.normpath(input))
            output_path = os.path.join(output, normal_path)
            self.print_process(build, output_path)
            if not os.path.isdir(output_path):
                os.makedirs(output_path)

            # Generate intermediate files.
            for build_file in build_files:
                command = self.GCOV + " -ib "
                command += "'" + os.path.abspath(build_file) + "'"
                # Change directory to output, since gcov outputs there.
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
        [shutil.copy(os.path.join(result, f), output)
                     for f in result_files]
        del profiles[0] # Already processed.

        for profile in profiles:
            profile_files = set(os.listdir(profile))
            unmatched = profile_files - set(result_files)
            matched = profile_files & set(result_files)

            for uprofile in unmatched:
                uprofile_path = os.path.join(profile, uprofile)
                self.print_copy(uprofile_path, output)
                shutil.copy(uprofile_path, output)
            result_files.extend(unmatched)

            for mprofile in matched:
                output_path = os.path.join(output, mprofile)
                profile_path = os.path.join(profile, mprofile)
                self.print_process(profile_path, output_path)
                operation(output_path, profile_path)

    def intersection(self, a, b): pass
    def difference(self, a, b): pass
    def union(self, a, b): pass
    def report(self, a, b): pass

    def print_crawl(self, folder):
        message = "crawling "
        message += "'" + folder  + "'"
        print(message)
    def print_copy(self, origin, destination):
        message = "copying "
        message += "'" + origin + "' to "
        message += "'" + destination + "'"
        print(message)
    def print_remove(self, path):
        message = "removing "
        message += "'" + path + "'"
        print(message)
    def print_process(self, folder, output):
        message = "processing "
        message += "'" + folder + "' to "
        message += "'" + output + "'"
        print(message)



INIT_ERROR_STATE = -1
if __name__ == "__main__":
    status = INIT_ERROR_STATE
    with ScovatScript() as tool:
        status = tool.execute()
    sys.exit(status)
