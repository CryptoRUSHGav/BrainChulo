from dotenv import load_dotenv
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings, HuggingFaceInstructEmbeddings
from langchain.text_splitter import CharacterTextSplitter, TokenTextSplitter, RecursiveCharacterTextSplitter
from langchain import HuggingFacePipeline
from colorama import Fore, Style
from transformers import BertTokenizerFast, BertForSequenceClassification
from langchain.vectorstores import Chroma
from langchain.docstore.document import Document
from langchain.llms import LlamaCpp
import torch
import re
import os


load_dotenv()

TEST_FILE = os.getenv("TEST_FILE")
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL")

EMBEDDINGS_MAP = {
    **{name: HuggingFaceInstructEmbeddings for name in ["hkunlp/instructor-xl", "hkunlp/instructor-large"]},
    **{name: HuggingFaceEmbeddings for name in ["all-MiniLM-L6-v2", "sentence-t5-xxl"]}
}

model_type = os.environ.get('MODEL_TYPE')
model_path = os.environ.get('MODEL_PATH')
model_n_ctx =1000
target_source_chunks = os.environ.get('TARGET_SOURCE_CHUNKS')
n_gpu_layers = os.environ.get('N_GPU_LAYERS')
use_mlock = os.environ.get('USE_MLOCK')
n_batch = os.environ.get('N_BATCH') if os.environ.get('N_BATCH') != None else 512
callbacks = []
qa_prompt = ""

CHROMA_SETTINGS = {}  # Set your Chroma settings here

def clean_text(text):
    # Remove line breaksRetrievalQA
    text = text.replace('\n', ' ')

    # Remove special characters
    text = re.sub(r'[^\w\s]', '', text)
    
    return text

def load_unstructured_document(document: str) -> list[Document]:
    with open(document, 'r') as file:
        text = file.read()
    title = os.path.basename(document)
    return [Document(page_content=text, metadata={"title": title})]

def split_documents(documents: list[Document], chunk_size: int = 250, chunk_overlap: int = 20) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return text_splitter.split_documents(documents)

 

def ingest_file(file_path):
        # Load unstructured document
        documents = load_unstructured_document(file_path)

        # Split documents into chunks
        documents = split_documents(documents, chunk_size=250, chunk_overlap=100)

        # Determine the embedding model to use
        EmbeddingsModel = EMBEDDINGS_MAP.get(EMBEDDINGS_MODEL)
        if EmbeddingsModel is None:
            raise ValueError(f"Invalid embeddings model: {EMBEDDINGS_MODEL}")

        model_kwargs = {"device": "cuda:0"} if EmbeddingsModel == HuggingFaceInstructEmbeddings else {}
        embedding = EmbeddingsModel(model_name=EMBEDDINGS_MODEL, model_kwargs=model_kwargs)

        # Store embeddings from the chunked documents
        vectordb = Chroma.from_documents(documents=documents, embedding=embedding)

        retriever = vectordb.as_retriever(search_kwargs={"k":4})

        print(file_path)
        print(retriever)

        return retriever

def classify_sentence(model, tokenizer, sentence):
    # Prepare the sentence for BERT by tokenizing, padding and creating attention mask
    print("FUNCTION STARTED")
    tokenizer = BertTokenizerFast.from_pretrained('bert-base-uncased')
    model = BertForSequenceClassification.from_pretrained('/home/karajan/labzone/ChatGPT_Automation/results/checkpoint-13500')
    encoding = tokenizer.encode_plus(
      sentence,
      truncation=True,
      padding='max_length',
      max_length=128,
      return_tensors='pt'  # Return PyTorch tensors
    )
    # Get the input IDs and attention mask in tensor format
    input_ids = encoding['input_ids']
    attention_mask = encoding['attention_mask']

    # No gradient needed for inference, so wrap in torch.no_grad()
    with torch.no_grad():
        # Forward pass, get logit predictions
        outputs = model(input_ids, attention_mask=attention_mask)
    print(outputs)
    # Get the predicted class
    _, predicted = torch.max(outputs.logits, 1)
    
    # Return the predicted class (0 for 'declarative', 1 for 'interrogative')
    return 'declarative' if predicted.item() == 0 else 'interrogative'



def load_tools():  
    #llm = LlamaCpp(model_path=model_path, n_ctx=model_n_ctx, callbacks=callbacks, verbose=False,n_gpu_layers=n_gpu_layers, use_mlock=use_mlock,top_p=0.9, n_batch=n_batch)

    def ingest_file(file_path):
        # Load unstructured document
        documents = load_unstructured_document(file_path)

        # Split documents into chunks
        documents = split_documents(documents, chunk_size=120, chunk_overlap=20)

        # Determine the embedding model to use
        EmbeddingsModel = EMBEDDINGS_MAP.get(EMBEDDINGS_MODEL)
        if EmbeddingsModel is None:
            raise ValueError(f"Invalid embeddings model: {EMBEDDINGS_MODEL}")

        model_kwargs = {"device": "cuda:0"} if EmbeddingsModel == HuggingFaceInstructEmbeddings else {}
        embedding = EmbeddingsModel(model_name=EMBEDDINGS_MODEL, model_kwargs=model_kwargs)

        # Store embeddings from the chunked documents
        vectordb = Chroma.from_documents(documents=documents, embedding=embedding)

        retriever = vectordb.as_retriever(search_kwargs={"k":4})

        print(file_path)
        print(retriever)

        return retriever, file_path

    file_path = TEST_FILE
    retriever, title = ingest_file(file_path)


    dict_tools = {
        'File Ingestion': ingest_file,
    }

    return dict_tools
