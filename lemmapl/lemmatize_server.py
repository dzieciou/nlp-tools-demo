from flask import Flask, request
from lemmapl2 import lemmatize_file

app = Flask(__name__)

def do_lemmatize(text):
    in_fpath = 'in_tmp.txt'
    with open(in_fpath, 'w', encoding='utf-8') as f:
        f.write(text)


@app.route('/', methods=['POST'])
def lemmatize():
    text = request.get_data()
    logging.getLogger().debug("Text:" + text)
    input_file = 'text_input.txt'
    output_file = 'text_output.xml'
    with open(input_file, 'w') as f:
        f.write(text)
    lemmatize_file(input_file=input_file, output_file=output_file)
    # TODO it would be better to parse XCES instead
    with open(output_file, 'r') as f:
        text_output = f.read()
    return text_output

if __name__ == "__main__":
    import logging
    logging.basicConfig(filename='error.log',level=logging.DEBUG)
    app.run(host='0.0.0.0', debug=True)