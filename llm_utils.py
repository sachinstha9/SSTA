import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_nm = "mistralai/Mistral-7B-Instruct-v0.3" if device == "cuda" else "Qwen/Qwen2-0.5B"
    tokenizer = AutoTokenizer.from_pretrained(model_nm, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if device == "cuda":
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_nm,
            quantization_config=bnb_config,
            device_map="auto",
            torch_dtype=torch.float16,
            trust_remote_code=True,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_nm,
            device_map=None,
            torch_dtype=torch.float32,
            trust_remote_code=True,
        )
    return tokenizer, model, device

def generate_explanation(summary_for_llm, tokenizer, model, device, max_tokens=500):
    prompt = f"""
The following is a solar forecast summary and user consumption data:
{json.dumps(summary_for_llm, indent=2)}

Explain in clear human-readable language:
1. Why solar generation may be insufficient on certain days.
2. Why solar generation may be sufficient or high on certain days.
Use cloud cover, precipitation, and low/high generation hours to justify.
"""
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=0.7,
            do_sample=True,
            top_p=0.9
        )
    explanation = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    return explanation

def answer_user_question(summary_for_llm, question, tokenizer, model, device, max_tokens=200):
    chat_prompt = f"""
Solar forecast summary: {json.dumps(summary_for_llm, indent=2)}
User question: {question}
Provide a clear human-readable answer.
"""
    inputs = tokenizer(chat_prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=0.7,
            do_sample=True,
            top_p=0.9
        )
    return tokenizer.decode(output_ids[0], skip_special_tokens=True)
