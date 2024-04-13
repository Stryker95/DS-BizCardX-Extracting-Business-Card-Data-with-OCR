#pip install azure-cognitiveservices-vision-computervision

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
from PIL import Image
import os
import re
import streamlit as st
import pandas as pd
import psycopg2
from io import BytesIO
import uuid
#use uuid.uuid4 to generTE UNIQUE FILE Names for each uploaded file
import io

# Set your Azure Cognitive Services API key and endpoint
subscription_key = '*'
endpoint = '*'

# Authenticate the client
credentials = CognitiveServicesCredentials(subscription_key)
client = ComputerVisionClient(endpoint, credentials)


def perform_ocr(image_path):
    with open(image_path, "rb") as image_stream:
        # Perform OCR on the image
       
        result = client.recognize_printed_text_in_stream(image_stream)

        # Extract the text from the result
        
        text = ""
        for region in result.regions:
            for line in region.lines:
                for word in line.words:
                    text += word.text + " "

        
        return text
    


def extract_information(result):
    columns={'Company_name':[],'Card_Holder_Name_and_Designation':[],'Mobile_Number':[],
             'Email_address':[],'Website_Url':[],'Area':[],'City':[],'State':[],
             'Pincode':[]}

    for i in range(len(result)):
        if result[i].startswith("+") or (result[i].replace("-","").isdigit() and '-' in result[i]):
            columns["Mobile_Number"].append(result[i])

        elif "@" in result[i]:
            if result[i].endswith('.com'):
                columns["Email_address"].append(result[i])
            if not result[i].endswith('.com'):
                result[i]+='.com'
                columns["Email_address"].append(result[i])

        elif ("www" in result[i] and".com" in result[i]) or (result[i-1]=="www" and result[i].startswith(".") and (i+1)<len(result) and result[i+1]==(".com")):
            if result[i].startswith("www"):
                columns["Website_Url"].append(result[i])
            else:
                columns['Website_Url']=result[i-1] + result[i] + result[i+1]

        elif "TamilNadu" in result[i]:
            columns['Pincode'].append(result[i+1])
            columns['State'].append(result[i])
            for j in range(i):
                if result[j].isdigit():
                    while j <i-1:   
                        columns["Area"].append(result[j])
                        j+=1

            columns["City"]=result[i-1]


    if 'www' not in result[len(result)-1]:
        columns['Company_name']=result[len(result)-2]+" "+result[len(result)-1]
        for i in range((5)):
            if not result[i].isdigit() and result[i].isalpha():
                columns['Card_Holder_Name_and_Designation'].append(result[i])
            else:
                break
    else:
        columns['Company_name']=result[0]+" "+result[1]
        columns['Card_Holder_Name_and_Designation']=result[2]+" "+result[3]+" "+result[4]

    return columns

# Remove square brackets, inverted commas, and curly brackets
def clean_value(value):
    if isinstance(value, list):
        return ', '.join(value)
    elif isinstance(value, str):
        return value.strip("'\"[]")
    else:
        return value
    
def upload_to_database(df_cleaned, uploaded_file,image_name):
    # Prepare the extracted information for database insertion
    company_name = df_cleaned['Company_name'].values[0]
    card_holder_name_and_designation = df_cleaned['Card_Holder_Name_and_Designation'].values[0]
    mobile_number = df_cleaned['Mobile_Number'].values[0]
    email_address = df_cleaned['Email_address'].values[0]
    website_url = df_cleaned['Website_Url'].values[0]
    area = df_cleaned['Area'].values[0]
    city = df_cleaned['City'].values[0]
    state = df_cleaned['State'].values[0]
    pincode = df_cleaned['Pincode'].values[0]  

    #connect to the postgre database
    conn = psycopg2.connect(
       host="localhost",
        database="ocr",
        user="postgres",
        password="Sanchit@1995",
        port="5432"
    )
    cursor = conn.cursor()
    
    #create the 'business_cards' table if it doesnt exist
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS business_cards(
                       id SERIAL PRIMARY KEY,
                       image_data BYTEA,
                       image_name VARCHAR,
                       company_name VARCHAR,
                       card_holder_name_and_designation VARCHAR,
                       mobile_number VARCHAR,
                       email_address VARCHAR,
                       website_url VARCHAR,
                       area VARCHAR,
                       city VARCHAR,
                       state VARCHAR,
                       pincode VARCHAR
                    )
                   """)
    # Read the image file as binary data
    image_data = psycopg2.Binary(uploaded_file.read())

    #insert the extracted information and image into the 'business_cards' table
    cursor.execute("""
                   INSERT INTO business_cards(image_data, image_name,company_name, card_holder_name_and_designation,
                                            mobile_number, email_address, website_url,
                                            area, city, state, pincode)
                    VALUES(%s, %s,%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (  image_data, image_name,
                        company_name, card_holder_name_and_designation,
                        mobile_number, email_address, website_url, area,
                        city, state, pincode))
                
    conn.commit()
    cursor.close()
    conn.close()

    return "Data uploaded to database successfully"
    
def get_uploaded_files_from_database():
    conn=psycopg2.connect(
        host="localhost",
        database="ocr",
        user="postgres",
        password="Sanchit@1995",
        port="5432"
    )
    cursor=conn.cursor()
    
    cursor.execute("SELECT image_name FROM business_cards;")
    rows = cursor.fetchall()
    uploaded_files = [row[0] for row in rows]
        
    return uploaded_files

def get_row_from_database(selected_file):
    conn = psycopg2.connect(
        host="localhost",
        database="ocr",
        user="postgres",
        password="Sanchit@1995",
        port="5432"
    )
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM business_cards WHERE image_name=%s", (selected_file,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()

    return row

def delete_row_from_database(id):
    conn = psycopg2.connect(
        host="localhost",
        database="ocr",
        user="postgres",
        password="Sanchit@1995",
        port="5432"
    )
    cursor = conn.cursor()
    cursor.execute("DELETE FROM business_cards where id=%s",(id,))
    conn.commit()
    conn.close()
    
def update_row_in_database(id, company_name, card_holder_name_and_designation, mobile_number, email_address, website_url, area, city, state, pincode):
    conn = psycopg2.connect(
        host="localhost",
        database="ocr",
        user="postgres",
        password="Sanchit@1995",
        port="5432"
    )
    cursor=conn.cursor()
    
    cursor.execute("""UPDATE business_cards
                    SET Company_name=%s,Card_Holder_Name_and_Designation=%s,
                    Mobile_Number=%s,Email_address=%s,Website_Url=%s,Area=%s,City=%s,
                    State=%s,Pincode=%s
                    WHERE id=%s""",
                    (company_name, card_holder_name_and_designation, mobile_number, email_address, website_url, area, city, state, pincode, id))
    
    conn.commit()

    
# Streamlit app

st.set_page_config(layout="wide")

st.title("Business Card Information Extraction")

# Define tabs
tabs = ["Upload Image and Extract Information", "Upload to Postgre Database","View/Edit Files"]
current_tab=st.sidebar.radio("Navigation",tabs)

#create 'uploads'directory if it doesnt exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Display content based on the selected tab

if current_tab == "Upload Image and Extract Information":
    uploaded_file = st.file_uploader( "",type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        file_name=f"{uuid.uuid4()}.{uploaded_file.name.split('.')[-1]}"
        temp_image_path = os.path.join("uploads", uploaded_file.name)
        with open(temp_image_path, "wb") as f:
            f.write(uploaded_file.read())
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_column_width=True)
        extracted_text = perform_ocr(temp_image_path)
        extracted_text = extracted_text.split()
        extracted_info = extract_information(extracted_text)
        df = pd.DataFrame.from_dict(extracted_info, orient='index').T
        df_cleaned = df.apply(lambda x: x.map(clean_value))
        st.table(df_cleaned)

elif current_tab == "Upload to Postgre Database":
    uploaded_file = st.file_uploader("", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        image_name = uploaded_file.name
        temp_image_path = os.path.join("uploads", uploaded_file.name)
        with open(temp_image_path, "wb") as f:
            f.write(uploaded_file.read())
            extracted_text = perform_ocr(temp_image_path)
            extracted_text = extracted_text.split()
            extracted_info = extract_information(extracted_text)
            df = pd.DataFrame.from_dict(extracted_info, orient='index').T
            df_cleaned = df.apply(lambda x: x.map(clean_value))
            result=upload_to_database(df_cleaned, uploaded_file,image_name)
            st.write(result)
            st.success("Data uploaded to database successfully")
            
elif current_tab=="View/Edit Files":
    uploaded_files=get_uploaded_files_from_database()
    if not uploaded_files:
        st.info("No files uploaded yet.")
    else:
        selected_file=st.selectbox("Select File",uploaded_files)
        if selected_file:
            selected_row=get_row_from_database(selected_file)
            df_row = pd.DataFrame([selected_row], columns=['id', 'image_data', 'image_name', 'company_name',
                                                            'card_holder_name_and_designation', 'mobile_number',
                                                            'email_address', 'website_url', 'area', 'city', 'state',
                                                            'pincode'])
            st.table(df_row)
            if selected_row:
                id, image_data,image_name,company_name,card_holder_name_and_designation,mobile_number,email_address,website_url,area,city,state,pincode=selected_row
                #st.write("Image Name:{image_name}")
                #st.image(image_data,caption='Uploaded Image',use_column_width=True)
                st.markdown("Update or modify any data below")
                company_name=st.text_input("Company Name",company_name)
                card_holder_name_and_designation=st.text_input("Card Holder Name and Designation",card_holder_name_and_designation)
                mobile_number=st.text_input("Mobile Number",mobile_number)
                email_address=st.text_input("Area",area)
                city=st.text_input("City",city)
                state=st.text_input("State",state)
                pincode=st.text_input("Pincode",pincode)
                if st.button("Commit changes to Database"):
                    update_row_in_database(id,company_name,card_holder_name_and_designation,mobile_number,email_address,website_url,area,city,state,pincode)
                    st.success("Information updated in database successfully.")
                
                if st.button("Delete"):
                    delete_row_from_database(id)
                    st.success("Information deleted from database successfully.")
                    
            else:
                st.warning("No data found for selected file.")
            
