import os
import sys

from snakemake import load_configfile
from csv import DictReader

config = load_configfile('analysis.yaml')


def get_callers():
    """Get a list of SV callers enabled by a user.
    """
    callers = []
    for c in config["enable_callers"]:
        if c not in config["callers"]:
            raise AssertionError("SV caller '{}' is not supported!".format(c))
        callers.append(c)
    return callers


def get_filext(fmt):
    """Get file extension(s) given file type/format:
        ['fasta', 'fasta_idx', 'bam', 'bam_idx', 'vcf', 'bcf', 'bed']
    """
    if fmt not in config["file_exts"].keys():
        raise AssertionError("Unknown input file format '{}'.".format(fmt.lower()))
    return config["file_exts"][fmt]


def get_fasta():
    """Get reference genome in FASTA.
    """
    fname = config["genome"]
    sfx = get_filext("fasta")
    try:
        if not os.path.exists(fname):
            raise AssertionError("FASTA file not found: {}.".format(fname))
        if not fname.endswith(sfx):
            raise AssertionError("FASTA file '{}' (extension) not registered.".format(fname))
    except AssertionError as err:
        print(str(err), file=sys.stderr)
        os._exit(1)
    return fname


def get_faidx():
    """Get FASTA index files generated by faidx and bwa tools.
    """
    faidx = []
    for sfx in get_filext("fasta_idx"):
        fname = get_fasta().split(get_filext("fasta"))[0] + sfx
        try:
            if not os.path.exists(fname):
                raise AssertionError("FASTA index file not found: {}.".format(fname))
        except AssertionError as err:
            print(str(err), file=sys.stderr)
            os._exit(1)
        faidx.append(fname)
    return faidx


def exclude_regions():
    """Check flag for excluding genomic regions (using a BED file).
    """
    excl = config["exclude_regions"]
    try:
        if excl not in (0, 1):
            raise AssertionError("Invalid value: 'exclude_regions' must be either 0 or 1.")
    except AssertionError as err:
        print(str(err), file=sys.stderr)
        os._exit(1)
    return excl


def get_bed():
    """Return BED filepath.
    """
    fname = config["exclusion_list"]
    sfx = get_filext("bed")
    try:
        if not os.path.exists(fname):
            raise AssertionError("Exclusion file not found: {}.".format(fname))
        if not fname.endswith(sfx):
            raise AssertionError("Exclusion file '{}' must end with '{}' suffix.".format(fname, sfx))
    except AssertionError as err:
        print(str(err), file=sys.stderr)
        os._exit(1)
    return fname


def get_bam(sample):
    sfx = get_filext("bam")
    if sample.endswith(sfx) is False:
        sample += sfx
    return sample


def get_bai(sample):
    sfx = get_filext("bam_idx")
    if sample.endswith(sfx) is False:
        sample += sfx
    return sample


def get_outdir(caller):
    """Get the caller's output directory.
    """
    return config["callers"][caller]["outdir"]


def get_nthreads(caller):
    """Get the number of threads used by a caller.
    """
    if "threads" in config["callers"][caller]:
        return config["callers"][caller]["threads"]
    else:
        return 1  # default: one thread


def get_memory(caller):
    """Get the amount of allocated memory (MB) by a caller.
    """
    if "memory" in config["callers"][caller]:
        return config["callers"][caller]["memory"]
    else:
        return 1024  # default: 1GB


def get_tmpspace(caller):
    """Get the amount of temporary disk space (MB) requested by a caller.
    """
    if "tmpspace" in config["callers"][caller]:
        return config["callers"][caller]["tmpspace"]
    else:
        return 0  # default: no temp space


def is_tumor_only():
    """Check if Manta should perform tumor-only or germline analysis.
    """
    val = config["callers"]["manta"]["tumor_only"]
    try:
        if val not in (0, 1):
            raise AssertionError("Incorrect value for Manta 'tumor_only': must be either 0 or 1.")
    except AssertionError as err:
        print(str(err), file=sys.stderr)
        os._exit(1)
    return val


def make_output():
    """Generate workflow targets or output files (.vcf) from callers.
    """
    def is_ok(s):
        if s in (None, ""):
            return False
        return s

    with open(config["samples"], "r") as fp:
        mode = config["mode"]
        try:
            if mode not in ('s', 'p'):
                raise AssertionError("Invalid workflow mode: run (s)ingle- or (p)aired-samples analysis.")
        except AssertionError as err:
            print(str(err), file=sys.stderr)
            os._exit(1)

        reader = DictReader(line for line in fp if not line.startswith("#"))
        outfiles = []
        for i, r in enumerate(reader):
            try:
                path = os.path.join(r["PATH"], is_ok(r["SAMPLE1"]))
                if mode.startswith('p') is True:  # for paired-samples
                    path += "--" + is_ok(r["SAMPLE2"])
            except TypeError as err:
                print("Missing value(s) in '{}' at record #{}: {}"
                      .format(config["samples"], i + 1, list(r.values())),
                      file=sys.stderr)
                os._exit(1)

            for c in get_callers():
                # PATH/SAMPLE1[--SAMPLE2]/CALLER_OUTDIR/survivor/CALLER.vcf
                vcf = c + get_filext("vcf")
                vcf = os.path.join(path, get_outdir(c), "survivor", vcf)
                outfiles.append(vcf)
        return outfiles


def make_all():
    """Generate workflow targets or output files (.vcf) merged over calers.
    """
    merged_outfiles = []
    for f in make_output():
        path = os.path.join(os.sep.join(f.split(os.sep)[:-3]), "all.vcf")
        merged_outfiles.append(path)
    return set(merged_outfiles)
