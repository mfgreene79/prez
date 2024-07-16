from openai import OpenAI
import csv
import os
import time
import logging
import yaml
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# Set up your OpenAI API key
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to load configuration from YAML file
def load_config(config_file='config.yaml'):
    logging.info("Loading configuration from YAML file.")
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

# Function to get a list of US Presidents and their dates of office
"""
#prompt =List all US Presidents, one on each line with no additional information. Ex:
#George Washington
#John Adams
"""

def get_presidents_info(model, prompt):
    logging.info("Fetching list of individuals.")
    try:
        response = client.chat.completions.create(model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ])
        content = response.choices[0].message.content
        presidents_list = []
        for line in content.split("\n"):
            if line.strip():  # Skip empty lines
                president = line.strip()
                presidents_list.append(president)
        logging.info("Successfully fetched list.")
        return presidents_list
    except openai.OpenAIError as e:
        logging.error(f"Error fetching presidents info: {e}")
        return []

# Function to ask questions about each president
def ask_questions(president, questions, policy_questions, model):
    answers = {}
    for question_data in questions:
        key = question_data['key']
        question = question_data['question'].format(president=president)
        logging.info(f"Asking question: {question}")
        try:
            response = client.chat.completions.create(model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ])
            answers[key] = response.choices[0].message.content
            logging.info(f"Received answer for question: {question}")
        except openai.OpenAIError as e:
            logging.error(f"Error fetching answer for '{question}': {e}")
            answers[key] = ""

    # Ask for policy questions that need to be split apart
    for question_data in policy_questions:
        key_base = question_data['key_base']
        question = question_data['question'].format(president=president)
        logging.info(f"Asking policy question: {question}")
        try:
            policy_response = client.chat.completions.create(model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ])
            policy_answer = policy_response.choices[0].message.content
            # Split the response into two policy issues
            policy_issues = policy_answer.split(";")
            answers[f"{key_base} 1"] = policy_issues[0].strip() if len(policy_issues) > 0 else ""
            answers[f"{key_base} 2"] = policy_issues[1].strip() if len(policy_issues) > 1 else ""
            logging.info(f"Received policy answers for question: {question}")
        except openai.OpenAIError as e:
            logging.error(f"Error fetching policy answer for '{question}': {e}")
            answers[f"{key_base} 1"] = ""
            answers[f"{key_base} 2"] = ""
        time.sleep(1)  # Add delay to handle rate limiting
    return answers

# Function to generate CSV fieldnames
def generate_fieldnames(questions, policy_questions):
    fieldnames = ['President', 'Model Used', 'Timestamp']
    for question_data in questions:
        fieldnames.append(question_data['key'])
    for question_data in policy_questions:
        fieldnames.append(f"{question_data['key_base']} 1")
        fieldnames.append(f"{question_data['key_base']} 2")
    return fieldnames

# Function to write results to CSV
def write_to_csv(presidents_list, questions, policy_questions, config):
    logging.info(f"Writing results to CSV file: {config['csv_file']}")
    fieldnames = generate_fieldnames(questions, policy_questions)
    with open(config['csv_file'], 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Ask questions and write results to CSV
        for idx, president in enumerate(presidents_list, 1):
            logging.info(f"Processing {idx}/{len(presidents_list)}: {president}")
            answers = ask_questions(president, questions, policy_questions, config['model'])
            row = {
                'President': president,
                'Model Used': config['model'],
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            row.update(answers)
            writer.writerow(row)
            logging.info(f"Written data for: {president}")

    logging.info(f"Finished writing results to CSV file: {config['csv_file']}")

# Main function
def main():
    # Load configuration from YAML file
    config = load_config('config_migov.yaml')

    # Get the list of presidents and their dates of office
    presidents_list = get_presidents_info(config['model'], config['prompt'])

    if not presidents_list:
        logging.error("Failed to retrieve presidents info. Exiting.")
        return

    # Write results to CSV
    if config['ask_policy'] == 'yes':
        write_to_csv(presidents_list, config['questions'], config['policy_questions'], config)
    else:
        write_to_csv(presidents_list, config['questions'], [], config)

if __name__ == "__main__":
    main()
