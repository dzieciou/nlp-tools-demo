#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import operator
import os
import re
import shutil
import sys
import tempfile
from optparse import OptionParser
from subprocess import call

import corpus2
import morfeusz2
from sets import Set


def get_script_path():
    return os.path.dirname(os.path.realpath(__file__))


class Feat:
    CAPITALIZED = "capitalized"
    ALL_CAPS = "all caps"
    NAMED_ENTITY = "named entity"
    NE_AROUND = "named entity around"
    COMMON = "common"
    SENT_BEGIN = "beginning of sentence"
    SENT_END = "end of sentence"
    FULL_STOP = "ending in full stop"
    CAP_AROUND = "words around capitalized"
    FROM_GROUPS = "analysis from shallow parser"
    INTERP = "interp"

    @staticmethod
    def token_features(str):
        features = []
        if str.isupper() and len(str) == 1:
            features.append(Feat.ALL_CAPS)
            features.append(Feat.CAPITALIZED)
        elif str.isupper():
            features.append(Feat.ALL_CAPS)
        elif str[0].isupper():
            features.append(Feat.CAPITALIZED)

        return features


class Interpretation:
    def __init__(self, lemma, type, features, orth, tagger_lemma):
        self.lemma = lemma
        self.type = type
        self.features = features
        self.orth = orth
        self.tagger_lemma = tagger_lemma


class Lematyzator:
    def __init__(self, morfeusz, freq_provider, abbrev_provider, tagset,
        ne_names=['imię', 'nazwisko']):
        self.morfeusz = morfeusz
        self.freq_provider = freq_provider
        self.abbrev_provider = abbrev_provider
        self.ne_names = ne_names
        self.identified_lemmas = dict()
        self.input_format = 'xces'
        self.tagset = tagset

    def update_dict(self, lemma):
        if lemma in self.identified_lemmas:
            self.identified_lemmas[lemma] = self.identified_lemmas[lemma] + 1
        else:
            self.identified_lemmas[lemma] = 1

    def update_features(self, interp, features):
        feats = list(features)
        # Named entities
        interp_name = interp.getName(self.morfeusz).decode('utf-8')
        if interp_name in self.ne_names:
            feats.append(Feat.NAMED_ENTITY)

        return feats

    def update_token_lemma(self, token, interp):
        lexemes = token.lexemes()
        if len(lexemes) > 0:
            if lexemes[0]:
                lexemes[0].set_lemma_utf8(interp.lemma.encode('utf8'))

    def lemmatize_document(self, filename):
        first_pass = []
        reader = corpus2.TokenReader.create_path_reader(self.input_format,
                                                        self.tagset, filename)

        idx = 0
        interpreted_tokens = []
        sentence = []
        while True:
            sent = reader.get_next_sentence()
            if not sent:
                break
            sentence.append(sent)
            interpreted_tokens.append(self.lemmatize_sentence(sent))
            idx = idx + 1

        interpreted_document = []
        for i in range(idx):
            sent_len = sentence[i].size()
            for tok in range(sent_len):
                interpretation = interpreted_tokens[i][tok]
                if (interpretation.type == 'freqs') or (
                    interpretation.type == 'guess'):
                    hint_interp = self.lemmatize(interpretation.orth,
                                                 interpretation.tagger_lemma,
                                                 interpretation.features, True)
                    if hint_interp:
                        self.update_token_lemma(sentence[i].tokens()[tok],
                                                hint_interp)

        return sentence

    def get_naked_lemma(self, lemma):
        if lemma == ':':
            return lemma

        return lemma.split(":")[0]

    def lemmatize_sentence(self, sentence):
        interpreted_tokens = []
        sent_len = sentence.size()
        # NE flag
        next_ne_around = False
        for i in range(sent_len):
            tok = sentence.tokens()[i]

            tagger_lemma = str(tok.lexemes()[0].lemma())
            tagger_lemma = tagger_lemma.decode('utf8')

            features = Feat.token_features(tok.orth_utf8())
            if tagger_lemma.startswith('_'):
                features.append(Feat.FROM_GROUPS)
                tagger_lemma = tagger_lemma[1:]

            if i == 0:
                features.append(Feat.SENT_BEGIN)
            elif i == sent_len - 1:
                features.append(Feat.SENT_END)

            if sent_len > i + 1:
                if sentence.tokens()[i + 1].orth_utf8() == '.':
                    features.append(Feat.FULL_STOP)
                if Feat.CAPITALIZED in Feat.token_features(
                    sentence.tokens()[i + 1].orth_utf8()):
                    features.append(Feat.CAP_AROUND)

            if i > 0:
                if Feat.CAPITALIZED in Feat.token_features(
                    sentence.tokens()[i - 1].orth_utf8()):
                    features.append(Feat.CAP_AROUND)

            if next_ne_around:
                features.append(Feat.NE_AROUND)
                next_ne_around = False

            interpreted_token = self.lemmatize(tok.orth_utf8(), tagger_lemma,
                                               features)

            if Feat.NAMED_ENTITY in interpreted_token.features:
                if i > 0:
                    interpreted_tokens[-1].features.append(Feat.NE_AROUND)
                    interpreted_tokens[-1].type = 'guess'
                if sent_len > i + 1:
                    next_ne_around = True

            self.update_token_lemma(tok, interpreted_token)
            interpreted_tokens.append(interpreted_token)

        return interpreted_tokens

    def lemmatize(self, orth, tagger_lemma, features, hint=False):
        # if (Feat.CAPITALIZED in features) and (Feat.NE_AROUND in features) \
        #   and (Feat.SENT_BEGIN not in features):
        #     return Interpretation(orth, 'ne', features, orth)

        # Abbreviations
        # if (Feat.FULL_STOP in features) and (Feat.SENT_END not in features):
        #   abbrev = self.abbrev_provider.get_abbrev(orth.lower().decode('utf-8'))
        #   if abbrev:
        #     return Interpretation(abbrev[0][0], 'abbrev', features, orth, tagger_lemma)

        res = self.morfeusz.analyse(orth)

        # Similar to previous lemmas (from hint)
        if hint:
            for interp in res:
                interp_lemma = self.get_naked_lemma(interp.lemma)
                if interp_lemma in self.identified_lemmas:
                    return Interpretation(interp.lemma, 'hint', features, orth,
                                          tagger_lemma)
            return None

        if Feat.FROM_GROUPS in features:
            return Interpretation(tagger_lemma, 'tagger', features, orth,
                                  tagger_lemma)

        # First interpretation from Morfeusz, which is the same caps
        # for interp in res:
        #   interp_lemma = interp.lemma.split(":")[0]
        #   lemma_feats = Feat.token_features(interp.lemma)
        #   if ((Feat.CAPITALIZED in features) and (Feat.CAPITALIZED in lemma_feats)) or \
        #   ((Feat.CAPITALIZED not in features) and (Feat.CAPITALIZED not in lemma_feats)):
        #     features = self.update_features(interp, features)
        #     return Interpretation(interp_lemma, 'guess', features, orth, tagger_lemma)

        # First interpretation from Morfeusz, which is capitalized
        for interp in res:
            lemma_feats = Feat.token_features(interp.lemma)
            if ((Feat.CAPITALIZED in features) and (
                Feat.CAPITALIZED in lemma_feats)):
                features = self.update_features(interp, features)
                return Interpretation(interp.lemma, 'guess', features, orth,
                                      tagger_lemma)

        # Frequency data
        if (len(res) > 1) and ((Feat.CAPITALIZED not in features) or (
            Feat.SENT_BEGIN in features)):
            lemma_set = Set()
            for result in res:
                interp_lemma = self.get_naked_lemma(result.lemma)
                lemma_set.add(interp_lemma)

            lemma_freq = self.freq_provider.get_freq(lemma_set)

            if lemma_freq:
                sorted_lemmas = sorted(lemma_freq.iteritems(),
                                       key=operator.itemgetter(1))
                return Interpretation(sorted_lemmas[-1][0], 'freqs', features,
                                      orth, tagger_lemma)

        for interp in res:
            interp_lemma = self.get_naked_lemma(interp.lemma)
            if interp_lemma == tagger_lemma:
                features = self.update_features(interp, features)
                return Interpretation(tagger_lemma, 'tagger', features, orth,
                                      tagger_lemma)

        if len(res) > 0:
            interp_lemma = self.get_naked_lemma(res[0].lemma)
            self.update_dict(interp_lemma)
            features = self.update_features(res[0], features)
            return Interpretation(interp_lemma, 'morfeusz', features, orth,
                                  tagger_lemma)

        return Interpretation(tagger_lemma, 'tagger_unk', features, orth,
                              tagger_lemma)


class FreqProvider:
    def __init__(self, freq_file):
        self.lemmas = []
        self.freqs = self.read_freqs(freq_file)

    def read_freqs(self, freq_file):
        with codecs.open(freq_file, 'r', encoding='utf8') as f:
            for line in f:
                col = line.split(",")
                if len(col) < 3:
                    continue

                total_count = 0
                lemma_dict = dict()
                for token in col:
                    token_split = token.split(":")
                    if len(token_split) < 2:
                        total_count = int(token_split[0])
                    else:
                        lemma_dict[token_split[0].lstrip()] = int(
                            token_split[1])

                for key in lemma_dict:
                    lemma_dict[key] = lemma_dict[key] / float(total_count)

                self.lemmas.append(lemma_dict)

    def get_freq(self, lemma_set):
        for lemma_dict in self.lemmas:
            passed = True
            for lemma in lemma_set:
                if lemma not in lemma_dict:
                    passed = False
                    break

            if passed == True:
                return lemma_dict

        return None


class AbbrevProvider:
    def __init__(self, abbrev_file):
        self.abbrevs = self.read_abbrevs(abbrev_file)

    def read_abbrevs(self, abbrev_file):
        abbrevs = dict()
        with codecs.open(abbrev_file, 'r', encoding='utf8') as f:
            current = None
            defs = []
            for line in f:
                trimmed = line.lstrip()
                if trimmed == line:
                    if len(defs) > 0:
                        abbrevs[current] = defs
                    current = trimmed.rstrip()
                    defs = []
                else:
                    m = re.search(u"(?<=skrót od: )(.*?)[\(;]", trimmed)
                    if not m:
                        m = re.search(u"(?<=skrót od: )(.*?)$", trimmed)

                    if m:
                        defs.append(m.groups())

        return abbrevs

    def get_abbrev(self, orth):
        if orth in self.abbrevs:
            return self.abbrevs[orth]
        else:
            return None


class RulesProvider:
    def __init__(self, abbrev_file):
        self.rules = self.read_rules(rules_file)

    def read_rules(self, rules_file):
        rules = []
        with codecs.open(rules_file, 'r', encoding='utf8') as f:
            for line in f:
                rules.append(line)

    def apply_rules(self, sentence):
        return None


def lemmatize_file(input_file, output_file, tagset='nkjp', verbose=True,
    maca_config='morfeusz-nkjp-official', data_dir='/data/model/wcrft',
    spejd_config='/data/spejd/config.ini', output_format='xces',
    preserve_temp=False):

    text_input = codecs.open(input_file, 'r', encoding='utf8')
    tagset = corpus2.get_named_tagset(tagset)

    temp_dir = tempfile.mkdtemp(dir='/tmp')
    with open(os.devnull, "w") as f:
        if verbose:
            call_out = None
        else:
            call_out = f

        # analyse plain text
        call(["maca-analyse", "-c", maca_config, "-o", "xces",
              "--output-file", temp_dir + '/_analysed.xml'], stdin=text_input,
             stdout=call_out, stderr=call_out)

        # tag input
        call(["wcrft-app", "-d", data_dir,
              "nkjp_s2.ini", temp_dir + "/_analysed.xml", "-O",
              temp_dir + "/_tagged.xml"],
             stdout=call_out, stderr=call_out)

        # spejd input
        call(["spejd", "-c", spejd_config,
             temp_dir + "/_tagged.xml"],
        stdout = call_out, stderr = call_out)

        call(["python", get_script_path() + "/groups2xces.py", temp_dir + "/ann_groups.xml",
              temp_dir + "/ann_words.xml"],
             stdout=call_out, stderr=call_out)

        call(["python", get_script_path() + "/tei2xces.py", temp_dir + "/ann_morphosyntax.xml",
              temp_dir + "/groups.xml"],
             stdout=call_out, stderr=call_out)

    morfeusz = morfeusz2.Morfeusz.createInstance()
    freq_provider = FreqProvider(get_script_path() + '/nkjp_freq.dat')
    abbrev_provider = AbbrevProvider(get_script_path() + '/abbrev.dat')

    with codecs.open(get_script_path() + '/ne_names.dat', 'r',
                     encoding='utf8') as f:
        ne_names = f.read().splitlines()

    lematyzator = Lematyzator(morfeusz, freq_provider, abbrev_provider, tagset,
                              ne_names)
    lemmatized = lematyzator.lemmatize_document(temp_dir + "/morph.xml")

    if output_file:
        writer = corpus2.TokenWriter.create_path_writer(
            output_format, output_file, tagset)
    else:
        writer = corpus2.TokenWriter.create_stdout_writer(
            output_format, tagset)

    new_chunk = corpus2.Chunk()
    for sent in lemmatized:
        new_chunk.append(sent.clone_shared())
    writer.write_chunk(new_chunk)
    writer.finish()

    if not preserve_temp:
        shutil.rmtree(temp_dir)


descr = """%prog [options] INPUTFILE

LemmaPL
(C) 2014, Institute of Computer Science, PAS

Uses a toolchain comprised of a morphological analyzer, a tagger and a
shallow parser to lemmatize text in Polish. Default output is stdout.
"""

if __name__ == '__main__':
    parser = OptionParser(usage=descr)
    parser.add_option('-k', '--keep', action='store_true', dest='preserve_temp',
                      help='preserve temporary files in a temp directory; default: false')
    parser.add_option('-d', '--data-dir', type='string', action='store',
                      dest='data_dir', default='/data/model/wcrft',
                      help='directory, in which WCRFT data model is located; default: /data/model/wcrft')
    # parser.add_option('-i', '--input-format', type='string', action='store',
    #   dest='input_format', default='xces',
    #   help='set the input format; default: xces')
    parser.add_option('-t', '--tagset', type='string', action='store',
                      dest='tagset', default='nkjp',
                      help='set the tagset used in input; default: nkjp')
    parser.add_option('-o', '--output-format', type='string', action='store',
                      dest='output_format', default='xces',
                      help='set the output format; default: xces')
    parser.add_option('-O', '--output-file', type='string', action='store',
                      dest='output_file',
                      help='set the output file name')
    parser.add_option('-c', '--config-maca', type='string', action='store',
                      default='morfeusz-nkjp-official', dest='maca_config',
                      help='maca configuration file, used during morphological analysis; default: morfeusz-nkjp-official')
    parser.add_option('-s', '--config-spejd', type='string', action='store',
                      dest='spejd_config',
                      default='/data/spejd/config.ini',
                      help='spejd configuration file; default: /data/spejd/config.ini')
    parser.add_option('-v', '--verbose', action='store_true',
                      help='print all intermediate messages')
    (options, args) = parser.parse_args()

    if len(args) < 1:
        sys.stderr.write('You need to provide the input file for processing\n')
        sys.stderr.write('See %s --help\n' % sys.argv[0])
        sys.stderr.write(get_script_path())
        sys.exit(1)

    text_file = args[0]
    lemmatize_file(input_file=text_file, output_file=options.output_file,
                   tagset=options.tagset,
                   verbose=options.verbose, maca_config=options.maca_config,
                   data_dir=options.data_dir, spejd_config=options.spejd_config,
                   output_format=options.output_format,
                   preserve_temp=options.preserve_temp)
