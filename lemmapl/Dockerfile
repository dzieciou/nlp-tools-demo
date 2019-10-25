FROM ipipan/langtools-all

RUN cd /root/lemmapl && \
   apt-get update && \
   apt-get -y install libssl-dev curl wget openssl && \
   curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
   python get-pip.py && \
   pip install Flask

COPY lemmapl2.py /root/lemmapl
COPY lemmatize_server.py /root/lemmapl

CMD python /root/lemmapl/lemmatize_server.py
