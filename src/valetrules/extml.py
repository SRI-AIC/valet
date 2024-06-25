from abc import abstractmethod
from frozendict import frozendict
import random
import re
from typing import Optional

import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader

# from aper import AveragedPerceptron, FeatureVector
from nlpcore.tokenizer import TokenSequence
from .manager import VRManager


class Embedding:

    def __init__(self, embedding_file=None):
        self.embedding_file = embedding_file
        self.embeddings = {}
        self.min = 0
        self.max = 0
        self.dim = None
        if embedding_file is not None:
            self.load_embeddings()

    def state_dict(self):
        return dict(embedding_file=self.embedding_file,
                    embeddings=self.embeddings,
                    min=self.min,
                    max=self.max,
                    dim=self.dim)

    @staticmethod
    def from_state_dict(state_dict):
        self = Embedding()
        self.embedding_file = state_dict['embedding_file']
        self.embeddings = state_dict['embeddings']
        self.min = state_dict['min']
        self.max = state_dict['max']
        self.dim = state_dict['dim']
        return self

    def load_embeddings(self):
        with open(self.embedding_file) as fh:
            for line in fh:
                line = line.rstrip()
                items = line.split(' ')
                values = [ float(x) for x in items[1:] ]
                self.dim = len(values)
                value = min(values)
                if value < self.min:
                    self.min = value
                value = max(values)
                if value > self.max:
                    self.max = value
                self.embeddings[ items[0] ] = values

    def embedding(self, word):
        word = word.lower()
        try:
            return self.embeddings[word]
        except KeyError:
            self.embeddings[word] = self.random_embedding()
            return self.embeddings[word]

    def random_embedding(self):
        return [ random.uniform(self.min, self.max) for _ in range(self.dim) ]


class Featurizer:

    ORTHO_FEATURES = [r'ing$', r'ed$', r's', r'^[A-Z]', r'^[A-Z]+$', r'^[a-z]+$']

    def __init__(self, extractor, word=True, embedding=True, dependencies=True, adjacency=1, orthographics=True):
        self.extractor = extractor
        self.word = word
        self.embedding = embedding
        self.dependencies = dependencies
        self.adjacency = adjacency
        self.orthographics = orthographics

    def features(self, example):
        feats = { ' bias ': 1 }
        self.add_word_features(feats, example)
        self.add_embedding_features(feats, example)
        if self.dependencies:
            self.add_dependency_features(feats, example)
        for i in range(1, self.adjacency + 1):
            self.add_adjacency_features(feats, example, i)
            self.add_adjacency_features(feats, example, -i)
        return frozendict(feats)

    def add_word_features(self, feats, example):

        if not self.word:
            return

        def add_feature(arg_code, word):
            word = word.lower()
            feats['%dw:%s' % (arg_code, word)] = 1

        if example.starti == example.endi:
            add_feature(0, example.start_word)
        else:
            add_feature(1, example.start_word)
            add_feature(2, example.end_word)

    def add_embedding_features(self, feats, example):

        if not self.embedding:
            return

        embeddings = self.extractor.embeddings

        def add_feature(arg_code, word):
            pass

    def add_dependency_features(self, feats, example):
        pass

    def add_adjacency_features(self, feats, example, offset):
        pass

class Example:

    def __init__(self, extractor, tseq: Optional[TokenSequence] = None, starti=None, endi=None):

        self.extractor = extractor
        # tseq is an AnnotatedTokenSequence object; tseq[i] := tseq.tokens[i]
        self.tseq = tseq
        self.starti = starti
        self.endi = endi

        self._features = None
        self._feature_vector = None

        if tseq is None:
            return

        anno = tseq.annotations
        self.start_pos = None
        self.end_pos = None
        self.start_lemma = None
        self.end_lemma = None

        if 'lemma' in anno:
            lemma = anno["lemma"]
            self.start_lemma = lemma[starti]
            self.end_lemma = lemma[endi]

        if 'pos' in anno:
            pos = anno["pos"]
            self.start_pos = pos[starti]
            self.end_pos = pos[endi]

        self.start_word = tseq[starti].lower()
        self.end_word = tseq[endi].lower()

        self.path = None
        if self.endi != self.starti:
            for path in tseq.find_paths(starti, endi):
                self.path = ' '.join(path)


    def state_dict(self):
        return { '_features': self._features }

    @staticmethod
    def from_state_dict(extractor, state_dict):
        self = Example(extractor)
        self._features = state_dict['_features']
        return self

    def __str__(self):
        return f'[{self.start_word} {self.path} {self.end_word}]'

    # This may need to be elaborated as the representation changes
    def __eq__(self, other):
        return isinstance(other, Example) and self.features() == other.features()

    def __hash__(self):
        return hash(self.features())

    def feature_vector(self):
        if self._feature_vector is not None:
            return self._feature_vector
        fv = self.extractor.feature_vector(self.features())
        self._feature_vector = fv
        return fv

    def features(self):
        if self._features is not None:
            return self._features

        feats = { ' bias ': 1}

        def add_deps(arg_code, toki, up):
            if up:
                dep_meth = 'get_up_dependencies'
            else:
                dep_meth = 'get_down_dependencies'
            for index, dep in getattr(self.tseq, dep_meth)(toki):
                if index == -1:
                    label = '%dudr:%s' % (arg_code, dep)
                else:
                    label = '%dud:%s' % (arg_code, dep)
                feats[label] = 1

        def add_word_feats(arg_code, word):
            word = word.lower()
            feats['%dw:%s' % (arg_code, word)] = 1
            for pat in self.WORD_FEATURES:
                if re.search(pat, word):
                    feats['%dwf:%s' % (arg_code, pat)] = 1
            emb = self.extractor.embeddings.embedding(word)
            for i, wt in enumerate(emb):
                feats['%demb:%d' % (arg_code, i)] = wt

        def add_adj_feats(arg_code, index, offs):
            adj_index = index + offs
            if adj_index < 0 or adj_index >= len(self.tseq):
                adj_word = '<oos>'
            else:
                adj_word = self.tseq[adj_index].lower()
            feats['%dadj%d:%s' % (arg_code, offs, adj_word)] = 1

        if self.starti == self.endi:
            feats[' ebias '] = 1
            add_word_feats(0, self.start_word)
            add_adj_feats(0, self.starti, -1)
            feats[f'0p:{self.start_pos}'] = 1
            add_deps(0, self.starti, True)
            add_deps(0, self.starti, False)
        else:
            feats[' rbias '] = 1
            feats[self.path] = 1
            add_word_feats(1, self.start_word)
            add_word_feats(2, self.end_word)
            add_adj_feats(1, self.starti, -1)
            add_adj_feats(2, self.endi, +1)
            feats[f'1p:{self.start_pos}'] = 1
            feats[f'2p:{self.end_pos}'] = 1
            add_deps(1, self.starti, True)
            add_deps(1, self.starti, False)
            add_deps(2, self.endi, True)
            add_deps(2, self.endi, False)
        self._features = frozendict(feats)
        return self._features


class Extractor:

    PATH_MATCHER_PREAMBLE = "ortho <- ortho.vrules\npath_matcher ~ connects(selected_paths, ortho.alpha, ortho.alpha)"

    def __init__(self, name=None, embedding=None):
        if name is not None:
            self.name = name
        self.vrm = VRManager(exception_on_redefinition=False)
        self.vrm.parse_block(self.PATH_MATCHER_PREAMBLE)
        if embedding is None:
            return
        self.embeddings = embedding
        self.training_paths = set()
        self.training_examples = {}
        self.training_annotations = []
        self.single_word_predictions = False

    def state_dict(self):
        return dict(name=self.name,
                    embeddings=self.embeddings.state_dict(),
                    training_paths=self.training_paths,
                    training_examples=[(example.state_dict(), value[0])
                                       for example, value in self.training_examples.items()],
                    training_annotations = [example.state_dict() for example in self.training_annotations],
                    single_word_predictions=self.single_word_predictions
                    )

    @staticmethod
    def from_state_dict(state_dict, **kwargs):
        self = Extractor()
        self.name = state_dict['name']
        self.embeddings = Embedding.from_state_dict(state_dict['embeddings'])
        self.training_paths = state_dict['training_paths']
        self.training_annotations = [Example.from_state_dict(self, e) for e in state_dict['training_annotations']]
        self.single_word_predictions = state_dict['single_word_predictions']
        if 'subclass' in kwargs:
            self.__class__ = kwargs['subclass']
        return self

    def refresh_training_examples(self, training_examples):
        self.training_examples = {}
        for ex_state, pos in training_examples:
            example = Example.from_state_dict(self, ex_state)
            self.training_examples[example] = (pos, example.feature_vector())

    def add_example(self, example, positive=True):
        if example in self.training_examples and self.training_examples[example][0]:
            print(example, "already marked positive; not adding")
            return False
        else:
            fv = example.feature_vector()
            #print(f"Adding example: {example},{positive}: {fv}")
            print(f"Adding example: {example},{positive}")
            self.training_paths.add(example.path)
            self.training_examples[example] = (positive, fv)
            self.training_annotations.append(example)
            '''
            print("EXAMPLES:")
            for example, feats in self.training_examples.items():
                print(f"{feats[0]}\t{example}")
            '''
            return True

    def pop_example(self):
        if len(self.training_annotations) == 0:
            print("No training examples")
        else:
            example = self.training_annotations.pop()
            del self.training_examples[example]
            if not any(ex for ex in self.training_examples.keys() if ex.path == example.path):
                self.training_paths.remove(example.path)

    def predictions(self, tseq: TokenSequence):
        preds = []
        for pred in self.relation_predictions(tseq):
            yield pred
            preds.append(pred)
        # Check if we do single-word prediction
        if not any(e for e in self.training_examples.keys() if e.starti == e.endi):
            return
        for pred in self.entity_predictions(tseq):
            example, _, _ = pred
            # Suppress entity prediction where relation already present
            if any(rex for rex, _, _ in preds if rex.starti <= example.starti <= rex.endi):
                continue
            yield pred

    def relation_predictions(self, tseq: TokenSequence):
        # Return all predictions, including those with score < 0
        paths = [p for p in self.training_paths if p is not None]
        if len(paths) == 0:
            return
        paths = ' | '.join(paths)
        self.vrm.parse_block("selected_paths ^ %s" % paths)
        for m in self.vrm.scan('path_matcher', tseq):
            if m.end <= m.begin:
                continue
            example = Example(self, tseq, m.begin, m.end-1)
            score = self.score(example)
            #print("   Relation: Score of %s is %f" % (example, score))
            yield example, score, example in self.training_examples

    def cached_relation_predictions(self, tseq: TokenSequence):
        # Version of above which caches previously found examples
        # Return all predictions, including those with score < 0
        if not hasattr(tseq, 'matches'):
            tseq.matches = {}
        for path in self.training_paths:
            if path is None:
                continue
            if path not in tseq.matches:
                # print(f"{tseq.id} {path}: new path")
                tseq.matches[path] = []
                self.vrm.parse_block(f"selected_paths ^ {path}")
                for m in self.vrm.scan("path_matcher", tseq):
                    if m.end <= m.begin:
                        continue
                    example = Example(self, tseq, m.begin, m.end-1)
                    tseq.matches[path].append(example)
            for example in tseq.matches[path]:
                yield example, self.score(example), example in self.training_examples

    def entity_predictions(self, tseq: TokenSequence):
        # Return all predictions, including those with score < 0
        for i in range(len(tseq)):
            example = Example(self, tseq, i, i)
            fv = example.feature_vector()
            score = self.score(fv)
            #print("   Entity: Score of %s is %f" % (example, score))
            yield example, score, example in self.training_examples

    @abstractmethod
    def feature_vector(self, example):
        raise NotImplementedError()

    @abstractmethod
    def train(self):
        raise NotImplementedError()

    @abstractmethod
    def score(self, feature_vector):
        raise NotImplementedError()


class MLP(nn.Module):

    def __init__(self, max_feats=1000):
        super().__init__()
        """
        self.layers = nn.Sequential(
            nn.Linear(max_feats, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 2),
        )
        """
        self.layers = nn.Sequential(
            nn.Linear(max_feats, 16),
            nn.ReLU(),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Linear(8, 2),
        )

    def forward(self, x):
        return self.layers(x)


class PaddedData(Dataset):

    def __init__(self, max_feats, feat_list, records):
        """
        :param records:  List of (target, feature dictionary)
        :param feat_list:
        """
        self.max_feats = max_feats
        self.feat_list = feat_list
        self.records = records
        self.n = len(records)

    def __len__(self):
        return self.n

    def __getitem__(self, idx):
        target, record = self.records[idx]
        return target, record


class MLPExtractor(Extractor):

    def __init__(self, name=None, embedding=None, max_feats=1000):
        super().__init__(name, embedding)
        self.max_feats = max_feats
        self.learner = MLP(max_feats)
        self.loss_function = nn.CrossEntropyLoss()
        self.optimizer = torch.optim.Adam(self.learner.parameters(), lr=1e-3)
        self.label_dict = { ' overflow ': 0 }
        self.label_list = [ ' overflow ' ]
        self.trained = False

    def state_dict(self):
        return dict(super=super().state_dict(),
                    max_feats=self.max_feats,
                    learner=self.learner.state_dict(),
                    optimizer=self.optimizer.state_dict(),
                    label_dict=self.label_dict,
                    label_list=self.label_list,
                    trained=self.trained)

    @staticmethod
    def from_state_dict(state_dict, **kwargs):
        self = Extractor.from_state_dict(state_dict['super'], subclass=MLPExtractor)
        self.max_feats = state_dict['max_feats']
        self.label_dict = state_dict['label_dict']
        self.label_list = state_dict['label_list']
        self.refresh_training_examples(state_dict['super']['training_examples'])
        self.loss_function = nn.CrossEntropyLoss()
        self.learner = MLP()
        self.learner.load_state_dict(state_dict['learner'])
        self.optimizer = torch.optim.Adam(self.learner.parameters(), lr=1e-3)
        self.optimizer.load_state_dict(state_dict['optimizer'])
        self.trained = state_dict['trained']
        return self

    def save(self, fname):
        torch.save(self.state_dict(), fname)

    @staticmethod
    def load(fname):
        state_dict = torch.load(fname)
        return MLPExtractor.from_state_dict(state_dict)

    def feature_index(self, feat):
        try:
            return self.label_dict[feat]
        except KeyError:
            fi = len(self.label_list)
            if fi >= self.max_feats:
                return 0
            else:
                self.label_dict[feat] = fi
                self.label_list.append(feat)
                return fi

    def feature_vector(self, features):
        ret = np.zeros(self.max_feats)
        for feature, weight in features.items():
            feature_index = self.feature_index(feature)
            ret[feature_index] = weight
        return torch.from_numpy(ret).float()

    def train(self):
        train_records = []
        for example, info in self.training_examples.items():
            true_class, fv = info
            train_records.append([int(true_class), fv])
        print(f"TRAIN: {len(self.label_list)} labels")
        data = PaddedData(self.max_feats, self.label_list, train_records)
        train_loader = DataLoader(data, batch_size=10, shuffle=True)
        for epoch in range(0, 100):
            current_loss = 0.0
            for data in train_loader:
                targets, inputs = data
                self.optimizer.zero_grad()
                outputs = self.learner(inputs)
                loss = self.loss_function(outputs, targets)
                loss.backward()
                self.optimizer.step()
                current_loss += loss.item()
            if epoch % 10 == 9:
                print(f"\tTrain epoch {epoch}: Loss {current_loss}")
        self.trained = True

    def score(self, example):
        if not self.trained:
            return 0
        feature_vector = example.feature_vector()
        output = self.learner(feature_vector)
        print(example, output)
        with torch.no_grad():
            _, prediction = torch.max(output.data, 0)
            return prediction   # prediction = 1 means positive; 0 means negative
