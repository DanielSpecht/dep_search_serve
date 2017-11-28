FROM ubuntu:17.04
WORKDIR /root

# Atuliza recursos do sistema e adiciona alguns requeridos pelo hunchentoot
RUN apt-get update && apt-get install -y make wget bzip2 && apt-get clean

RUN apt-get update -y

# Install Git
RUN apt-get install git -y

# Para servidores
RUN apt-get install libssl-dev -y

# Para encodings dos arquivos
RUN apt-get install language-pack-en-base -y

# TURKU dependencies, python libraries mostly
RUN apt-get install python-dev -y
RUN apt-get install sqlite3 libsqlite3-dev

RUN apt-get -y install python-pip

RUN pip install Cython
RUN pip install uwsgi
RUN pip install Flask
RUN pip install pyyaml
RUN pip install requests

RUN mkdir repositories

# Not made by git clone
ADD src/ repositories/dep_search_serve

CMD cd repositories/dep_search_serve \
    && python serve_depsearch.py

    





