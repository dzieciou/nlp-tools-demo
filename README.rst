Demo of NLP libraries for English and Polish
============================================

The goal of this repository is to demonstrate application of NLP libraries for typical NLP tasks in
English and Polish.

Libraries:

- `spaCy`_
- `NLTK`_
- `pystempel`_
- `LemmaPL`_ that chains three tools: `Morfeusz analyzer`_, `WCRFT tagger`_ and `Spejd parser`_.

.. _spaCy: https://spacy.io/
.. _NLTK: https://www.nltk.org/
.. _pystempel: https://pypi.org/project/pystempel/
.. _LemmaPL: http://zil.ipipan.waw.pl/LemmaPL
.. _Morfeusz analyzer: http://morfeusz.sgjp.pl/
.. _WCRFT tagger: http://nlp.pwr.wroc.pl/redmine/projects/wcrft/wiki
.. _Spejd parser: http://zil.ipipan.waw.pl/Spejd

Running examples
----------------

.. code:: console

  conda env create --file environment.yml
  conda activate nlp
  jupyter notebooks

Then go to ``examples/`` folder.
