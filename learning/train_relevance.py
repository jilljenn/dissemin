# -*- encoding: utf-8 -*-

# Dissemin: open access policy enforcement tool
# Copyright (C) 2014 Antonin Delpeuch
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

from __future__ import unicode_literals, print_function

from django.db.models import Q
from papers.models import *
from learning.model import *
from backend.relevance import *
from backend.clustering import *

# Stage of the learning process
# 0: no clustering has taken place before
# 1: one step of clustering has taken place before
#    … and so on
stage = 1

make_lm = False
recompute = True
train = True
cluster = False

# Read dataset
author_ids = []
labels = []
for line in open('learning/dataset/relevance_training_ids', 'r'):
    vals = map(lambda x: int(x), line.strip().split('\t'))
    author_ids.append((vals[0], Researcher.objects.get(pk=int(vals[1]))))
    labels.append(vals[2])

# These models are not re-trained at each step because they don't depend on the clustering output
all_fields_model = WordCount()
all_fields_model.load('models/everything.pkl')
contributors_model = WordCount()
contributors_model.load('models/contributors.pkl')
publications_model = WordCount()
publications_model.load('models/publications.pkl')
rc = SimpleRelevanceClassifier(languageModel=all_fields_model,
        contributorsModel=contributors_model,
        publicationsModel=publications_model)

# If this is the first stage, we reset all author attributions
if stage <= 0:
    print("Resetting author attributions…")
    for name in Name.objects.filter(is_known=True):
        try:
            r = Researcher.objects.get(name=name)
        except ObjectDoesNotExist:
            name.is_known = False
            name.save(update_fields=['is_known'])

        name.author_set.all().update(researcher=r)

if stage < 0:
    exit(0)

relevance_model_fname = 'models/relevance-'+str(stage)+'.pkl'

# Rebuild topic models for all the departments
if make_lm:
    print("Topic model")
    i = 0
    for author in Author.objects.filter(paper__visibility='VISIBLE', researcher__isnull=False).select_related('researcher'):
        if i % 100 == 0:
            print(i)
        rc.feed(author, author.researcher)
        i += 1
    rc.save(relevance_model_fname)
else:
    rc.load(relevance_model_fname)

# Recompute features for the relevance classifier training set
if recompute or make_lm:
    print("Computing features")
    features = []
    for (id,researcher) in author_ids:
        author = Author.objects.get(pk=id)
        f = rc.computeFeatures(author, researcher)
        features.append(f)
    print("Writing features back")
    outf = open('learning/dataset/relevance-features-'+str(stage), 'w')
    for i in range(len(features)):
        print('\t'.join(map(lambda x: str(x), features[i])), file=outf)
    outf.close()
elif train:
    inf = open('learning/dataset/relevance-features-'+str(stage), 'r')
    features = []
    for line in inf:
        f = map(lambda x: float(x), line.strip().split('\t'))
        features.append(f)
    inf.close()

# Train the classifier and show outliers
if train or recompute or make_lm:
    if stage > 0:
        rc.positiveSampleWeight = 0.27
    rc.train(features, labels, 'linear')

    def paper_url(pk):
        print('http://beta.ens.dissem.in/paper/'+str(Author.objects.get(pk=pk).paper_id))

    for i in range(len(labels)):
        prediction = rc.classifier.predict(features[i])[0]
        if labels[i] == 0 and prediction == 1:
            print("#####")
            paper_url(author_ids[i][0])
            print("Explanation")
            print(rc.computeFeatures(Author.objects.get(pk=author_ids[i][0]), author_ids[i][1], explain=True))

    print(rc.confusion(features, labels))
    rc.save(relevance_model_fname)

# Cluster all the researchers
if cluster:
    sc = SimilarityClassifier(filename="models/similarity.pkl")
    for r in Researcher.objects.all():
        cc = ClusteringContext(r, sc, rc)
        cc.reclusterBatch()
        cc.commit()
        print("That was researcher "+str(r.pk))

