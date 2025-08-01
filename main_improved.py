# Improved Job Application Automation
# Fixed version that handles existing accounts and better form filling

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementNotInteractableException, 
    StaleElementReferenceException, WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import re
from urllib.parse import urlparse
import sys
from config import PERSONAL_INFO, FILE_PATHS, APPLICATION_SETTINGS

def initialize_driver(headless=False):
    """Initialize Chrome WebDriver."""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
    
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(APPLICATION_SETTINGS["implicit_wait_time"])
    return driver

def find_and_fill_fields(driver):
    """Find and fill all input fields on the page."""
    print("INFO: Scanning for input fields...")
    
    # Get all input elements
    inputs = driver.find_elements(By.XPATH, 
        "//input[not(@type='hidden') and not(@readonly) and not(@disabled)] | "
        "//textarea[not(@readonly) and not(@disabled)] | "
        "//select[not(@disabled)]")
    
    print(f"INFO: Found {len(inputs)} input fields")
    
    # FIRST: Handle Country field specifically (highest priority)
    print("INFO: Prioritizing Country field...")
    country_filled = handle_country_field_first(driver)
    
    # Wait a moment for any form updates after country selection
    if country_filled:
        print("INFO: Country selected, waiting for form to update...")
        time.sleep(3)  # Increased wait time
        
        # Re-scan for input fields after form update
        print("INFO: Re-scanning for input fields after country selection...")
        inputs = driver.find_elements(By.XPATH, 
            "//input[not(@type='hidden') and not(@readonly) and not(@disabled)] | "
            "//textarea[not(@readonly) and not(@disabled)] | "
            "//select[not(@disabled)]")
        print(f"INFO: Found {len(inputs)} input fields after country selection")
    
    filled_count = country_filled
    
    # THEN: Fill other fields
    for i, input_elem in enumerate(inputs):
        try:
            # Check if element is still valid
            try:
                if not input_elem.is_displayed():
                    continue
            except:
                print(f"DEBUG: Element {i+1} became stale, skipping...")
                continue
            
            # Get field info
            field_type = input_elem.get_attribute('type') or 'text'
            field_id = input_elem.get_attribute('id') or ''
            field_name = input_elem.get_attribute('name') or ''
            field_placeholder = input_elem.get_attribute('placeholder') or ''
            field_aria_label = input_elem.get_attribute('aria-label') or ''
            field_title = input_elem.get_attribute('title') or ''
            current_value = input_elem.get_attribute('value') or ''
            
            # Skip if already has value
            if current_value.strip() and field_type not in ['select-one', 'radio', 'checkbox']:
                continue
            
            # Skip country field as it's already handled
            combined_text = f"{field_id} {field_name} {field_placeholder} {field_aria_label} {field_title}".lower()
            if any(word in combined_text for word in ['country', 'country/region']):
                continue
            
            # Get label - try multiple approaches
            label_text = ""
            
            # Try label for attribute
            try:
                if field_id:
                    label = driver.find_element(By.XPATH, f"//label[@for='{field_id}']")
                    label_text = label.text.strip()
            except:
                pass
            
            # Try parent label
            if not label_text:
                try:
                    parent_label = input_elem.find_element(By.XPATH, "./ancestor::label[1]")
                    label_text = parent_label.text.strip()
                except:
                    pass
            
            # Try sibling label
            if not label_text:
                try:
                    sibling = input_elem.find_element(By.XPATH, "./preceding-sibling::*[1]")
                    if sibling and sibling.text.strip():
                        label_text = sibling.text.strip()
                except:
                    pass
            
            # Try parent div with text
            if not label_text:
                try:
                    parent = input_elem.find_element(By.XPATH, "./..")
                    if parent and parent.text.strip():
                        parent_text = parent.text.strip()
                        # Extract first line as label
                        label_text = parent_text.split('\n')[0][:50]
                except:
                    pass
            
            # Combine all text for matching
            combined_text = f"{field_id} {field_name} {field_placeholder} {field_aria_label} {field_title} {label_text}".lower()
            
            # Match field to data with more comprehensive matching
            data_to_fill = None
            
            # More comprehensive matching patterns
            if any(word in combined_text for word in ['first name', 'firstname', 'given name', 'fname', 'given name(s)', 'first', 'given']):
                data_to_fill = PERSONAL_INFO.get('first_name')
            elif any(word in combined_text for word in ['last name', 'lastname', 'family name', 'surname', 'lname', 'family name*', 'last', 'family', 'surname']):
                data_to_fill = PERSONAL_INFO.get('last_name')
            elif any(word in combined_text for word in ['email', 'e-mail', 'email address', 'e-mail address']):
                data_to_fill = PERSONAL_INFO.get('email')
            elif any(word in combined_text for word in ['phone number', 'mobile', 'telephone', 'tel', 'phone']) and 'code' not in combined_text and 'extension' not in combined_text:
                data_to_fill = PERSONAL_INFO.get('phone')
            elif any(word in combined_text for word in ['address line 1', 'street address', 'address1', 'address line 1*', 'street']):
                data_to_fill = PERSONAL_INFO.get('address_line1')
            elif any(word in combined_text for word in ['address line 2', 'address2', 'address line 2*']):
                data_to_fill = PERSONAL_INFO.get('address_line2')
            elif any(word in combined_text for word in ['city', 'town','City']) and 'address' not in combined_text:
                data_to_fill = PERSONAL_INFO.get('city')
            elif any(word in combined_text for word in ['state', 'province']):
                data_to_fill = PERSONAL_INFO.get('state')
            elif any(word in combined_text for word in ['postal code', 'zip code', 'zipcode', 'zip', 'postal']):
                data_to_fill = PERSONAL_INFO.get('zip_code')
            elif any(word in combined_text for word in ['Linkedin', 'Linkedin profile', 'Linkedin URL','linkedin']):
                data_to_fill = PERSONAL_INFO.get('linkedin_url')
            elif any(word in combined_text for word in ['resume', 'cv', 'attach resume', 'upload resume', 'resume upload']):
                data_to_fill = FILE_PATHS.get('resume_path')
            elif any(word in combined_text for word in ['how did you hear', 'how did you hear about us', 'source', 'referral source']):
                data_to_fill = PERSONAL_INFO.get('how_heard')
            
            # For generic field IDs, try to infer from context
            if not data_to_fill and field_id and len(field_id) > 20:  # Generic ID
                # Look at surrounding context
                try:
                    # Get parent container text
                    parent_container = input_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'field') or contains(@class, 'form') or contains(@class, 'input')][1]")
                    container_text = parent_container.text.lower()
                    
                    # Match based on container text
                    if any(word in container_text for word in ['first', 'given']):
                        data_to_fill = PERSONAL_INFO.get('first_name')
                    elif any(word in container_text for word in ['last', 'family', 'surname']):
                        data_to_fill = PERSONAL_INFO.get('last_name')
                    elif any(word in container_text for word in ['email', 'mail']):
                        data_to_fill = PERSONAL_INFO.get('email')
                    elif any(word in container_text for word in ['phone', 'mobile', 'tel']):
                        data_to_fill = PERSONAL_INFO.get('phone')
                    elif any(word in container_text for word in ['address', 'street']):
                        data_to_fill = PERSONAL_INFO.get('address_line1')
                    elif any(word in container_text for word in ['city']):
                        data_to_fill = PERSONAL_INFO.get('city')
                except:
                    pass
            
            if data_to_fill:
                print(f"INFO: Filling field {i+1}: {label_text or field_name or field_id} with {data_to_fill}")
                
                # Fill the field with stale element handling
                try:
                    if field_type == 'file':
                        if os.path.exists(data_to_fill):
                            input_elem.send_keys(os.path.abspath(data_to_fill))
                            print(f"SUCCESS: Uploaded {data_to_fill}")
                            filled_count += 1
                    elif input_elem.tag_name == 'select':
                        try:
                            select = Select(input_elem)
                            # Try exact match first
                            try:
                                select.select_by_visible_text(data_to_fill)
                                print(f"SUCCESS: Selected {data_to_fill}")
                                filled_count += 1
                            except:
                                # Try partial match
                                options = [option.text for option in select.options]
                                for option in options:
                                    if data_to_fill.lower() in option.lower() or option.lower() in data_to_fill.lower():
                                        select.select_by_visible_text(option)
                                        print(f"SUCCESS: Selected {option} (partial match for {data_to_fill})")
                                        filled_count += 1
                                        break
                                else:
                                    print(f"WARNING: Could not find option matching {data_to_fill}")
                                    print(f"Available options: {options}")
                        except Exception as e:
                            print(f"WARNING: Could not select {data_to_fill}: {str(e)}")
                    else:
                        input_elem.clear()
                        input_elem.send_keys(data_to_fill)
                        print(f"SUCCESS: Filled with {data_to_fill}")
                        filled_count += 1
                except Exception as e:
                    print(f"ERROR: Could not fill field {i+1}: {str(e)}")
                    continue
            else:
                print(f"SKIP: Field {i+1} - {label_text or field_name or field_id} (no match)")
                
        except Exception as e:
            print(f"ERROR: Could not process field {i+1}: {str(e)}")
            continue
    
    # Handle other custom dropdown buttons (but not country)
    print("INFO: Checking for other custom dropdown buttons...")
    other_dropdown_filled = handle_other_custom_dropdowns(driver)
    filled_count += other_dropdown_filled
    
    print(f"INFO: Filled {filled_count} fields automatically")
    return filled_count

'''
def auto_select_radio_yes_no(driver):
    """Automatically select 'No' by clicking the label."""
    print("INFO: Checking for Yes/No radio groups...")

    radio_groups = driver.find_elements(By.XPATH, "//fieldset")

    for group in radio_groups:
        try:
            text = group.text.lower()
            if "worked for calix" in text or "previous employee" in text or "have you worked" in text:
                print(f"INFO: Detected Yes/No question: {text[:60]}...")

                # Find all labels inside this group
                labels = group.find_elements(By.XPATH, ".//label")

                for label in labels:
                    if "no" in label.text.strip().lower():
                        label.click()
                        print("SUCCESS: Selected 'No' by clicking label.")
                        return True

        except Exception as e:
            print(f"WARNING: Could not auto-select radio: {str(e)}")
            continue

    return False

'''
def auto_select_radio_yes_no(driver):
    print("INFO: Checking for Yes/No radio groups...")
    try:
        fieldsets = driver.find_elements(By.TAG_NAME, "fieldset")
        for fieldset in fieldsets:
            label_text = fieldset.text.strip().lower()
            if "have you worked" in label_text or "yes" in label_text and "no" in label_text:
                try:
                    no_label = fieldset.find_element(By.XPATH, ".//label[contains(text(), 'No')]")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", no_label)
                    no_label.click()
                    print("SUCCESS: Selected 'No' for Yes/No question")
                except Exception as inner_e:
                    print(f"WARNING: Could not select 'No': {inner_e}")
    except Exception as e:
        print(f"WARNING: Error while scanning radio groups: {e}")



def handle_country_field_first(driver):
    """Handle Country field with highest priority."""
    print("INFO: Looking for Country field specifically...")
    
    # Multiple selectors for Country field
    country_selectors = [
        "//button[contains(@aria-label, 'Country')]",
        "//button[contains(@aria-label, 'Region')]",
        "//button[contains(@aria-label, 'Country/Region')]",
        "//select[contains(@name, 'country')]",
        "//select[contains(@id, 'country')]",
        "//input[contains(@name, 'country')]",
        "//input[contains(@id, 'country')]",
        "//button[@aria-haspopup='listbox'][contains(text(), 'United States')]",
        "//button[@aria-haspopup='listbox'][contains(text(), 'America')]"
    ]
    
    for selector in country_selectors:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            for element in elements:
                if not element.is_displayed():
                    continue
                
                print(f"INFO: Found Country field: {element.text or element.get_attribute('aria-label')}")
                
                try:
                    if element.tag_name == 'button':
                        # Handle custom dropdown button
                        element.click()
                        time.sleep(1)
                        
                        # Look for India in dropdown options
                        options = driver.find_elements(By.XPATH, 
                            "//div[@role='option'] | //li[@role='option'] | //div[contains(@class, 'option')] | //li[contains(@class, 'option')]")
                        
                        if not options:
                            options = driver.find_elements(By.XPATH, 
                                "//div[contains(@class, 'menu')]//div | //ul[contains(@class, 'menu')]//li")
                        
                        # Find and click India with more precise matching
                        india_found = False
                        for option in options:
                            option_text = option.text.strip()
                            print(f"DEBUG: Checking option: '{option_text}'")
                            
                            # Exact match for "India" (not "British Indian Territory")
                            if option_text.lower() == 'india':
                                option.click()
                                print(f"SUCCESS: Selected India (exact match)")
                                india_found = True
                                break
                            # Check for "India" but not "British" or "Territory"
                            elif 'india' in option_text.lower() and 'british' not in option_text.lower() and 'territory' not in option_text.lower():
                                option.click()
                                print(f"SUCCESS: Selected {option_text} (India without British/Territory)")
                                india_found = True
                                break
                        
                        if not india_found:
                            print(f"WARNING: Could not find exact India option in dropdown")
                            print(f"Available options: {[opt.text for opt in options]}")
                            
                            # Ask user to select manually if no exact match
                            if not APPLICATION_SETTINGS["headless_mode"]:
                                print("Please select India manually from the dropdown and press Enter...")
                                input("Press Enter after selecting India...")
                                india_found = True
                            
                            # Close dropdown
                            driver.find_element(By.TAG_NAME, "body").click()
                        
                        return 1 if india_found else 0
                        
                    elif element.tag_name == 'select':
                        # Handle standard select
                        select = Select(element)
                        try:
                            # Try exact match first
                            select.select_by_visible_text('India')
                            print(f"SUCCESS: Selected India from select dropdown")
                            return 1
                        except:
                            # Try partial match but avoid British Indian Territory
                            for option in select.options:
                                option_text = option.text.strip()
                                if option_text.lower() == 'india':
                                    select.select_by_visible_text(option_text)
                                    print(f"SUCCESS: Selected {option_text} (exact match)")
                                    return 1
                                elif 'india' in option_text.lower() and 'british' not in option_text.lower() and 'territory' not in option_text.lower():
                                    select.select_by_visible_text(option_text)
                                    print(f"SUCCESS: Selected {option_text} (India without British/Territory)")
                                    return 1
                    
                except Exception as e:
                    print(f"ERROR: Could not handle Country field: {str(e)}")
                    continue
                
        except Exception as e:
            print(f"ERROR: Could not process Country selector {selector}: {str(e)}")
            continue
    
    print("WARNING: Could not find or fill Country field")
    return 0

def handle_other_custom_dropdowns(driver):
    """Handle other custom dropdown buttons (not Country)."""
    filled_count = 0
    
    # Look for other custom dropdown buttons (excluding Country)
    dropdown_selectors = [
        "//button[@aria-haspopup='listbox']",
        "//button[contains(@aria-label, 'State')]",
        "//button[contains(@aria-label, 'City')]",
        "//button[contains(@class, 'dropdown')]",
        "//button[contains(@class, 'select')]"
    ]
    
    for selector in dropdown_selectors:
        try:
            buttons = driver.find_elements(By.XPATH, selector)
            for button in buttons:
                if not button.is_displayed():
                    continue
                
                # Skip Country fields (already handled)
                button_text = button.text.strip()
                aria_label = button.get_attribute('aria-label') or ''
                if any(word in aria_label.lower() for word in ['country', 'region']):
                    continue
                
                # Get button info
                button_id = button.get_attribute('id') or ''
                
                # Determine what to fill based on button context
                data_to_fill = None
                combined_text = f"{button_text} {aria_label} {button_id}".lower()
                
                if any(word in combined_text for word in ['state', 'province']):
                    data_to_fill = PERSONAL_INFO.get('state')
                elif any(word in combined_text for word in ['city', 'town']):
                    data_to_fill = PERSONAL_INFO.get('city')
                
                if data_to_fill:
                    print(f"INFO: Found custom dropdown: {button_text} - filling with {data_to_fill}")
                    
                    try:
                        # Click the button to open dropdown
                        button.click()
                        time.sleep(1)
                        
                        # Look for the dropdown options
                        options = driver.find_elements(By.XPATH, 
                            "//div[@role='option'] | //li[@role='option'] | //div[contains(@class, 'option')] | //li[contains(@class, 'option')]")
                        
                        if not options:
                            # Try alternative selectors
                            options = driver.find_elements(By.XPATH, 
                                "//div[contains(@class, 'menu')]//div | //ul[contains(@class, 'menu')]//li")
                        
                        # Find and click the matching option
                        option_found = False
                        for option in options:
                            option_text = option.text.strip()
                            if option_text.lower() == data_to_fill.lower():
                                option.click()
                                print(f"SUCCESS: Selected {data_to_fill}")
                                filled_count += 1
                                option_found = True
                                break
                            elif data_to_fill.lower() in option_text.lower():
                                option.click()
                                print(f"SUCCESS: Selected {option_text} (partial match for {data_to_fill})")
                                filled_count += 1
                                option_found = True
                                break
                        
                        if not option_found:
                            print(f"WARNING: Could not find option '{data_to_fill}' in dropdown")
                            print(f"Available options: {[opt.text for opt in options]}")
                            
                            # Close dropdown if no match found
                            try:
                                # Try to click outside or press Escape
                                driver.find_element(By.TAG_NAME, "body").click()
                            except:
                                pass
                    
                    except Exception as e:
                        print(f"ERROR: Could not handle custom dropdown: {str(e)}")
                        # Try to close dropdown
                        try:
                            driver.find_element(By.TAG_NAME, "body").click()
                        except:
                            pass
                
        except Exception as e:
            print(f"ERROR: Could not process dropdown selector {selector}: {str(e)}")
            continue
    
    return filled_count

def handle_login(driver):
    """Handle login if required."""
    print("INFO: Checking if login is required...")
    
    # Check for login indicators
    page_text = driver.page_source.lower()
    login_indicators = ['login', 'signin', 'sign-in', 'sign in', 'email', 'password']
    
    if any(indicator in page_text for indicator in login_indicators):
        print("INFO: Login detected - please login manually")
        
        if not APPLICATION_SETTINGS["headless_mode"]:
            input("Press Enter after logging in...")
            time.sleep(3)
            return True
        else:
            print("WARNING: Cannot login manually in headless mode")
            return False
    
    return True

def handle_remaining_fields(driver):
    """Handle remaining required fields that couldn't be filled automatically."""
    print("INFO: Checking for remaining required fields...")
    
    # Look for required fields (usually marked with *)
    required_selectors = [
        "//input[contains(@class, 'required')]",
        "//select[contains(@class, 'required')]",
        "//textarea[contains(@class, 'required')]",
        "//input[contains(@placeholder, '*')]",
        "//select[contains(@placeholder, '*')]",
        "//textarea[contains(@placeholder, '*')]"
    ]
    
    remaining_fields = []
    for selector in required_selectors:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            for element in elements:
                if element.is_displayed():
                    current_value = element.get_attribute('value') or ''
                    if not current_value.strip():
                        remaining_fields.append(element)
        except:
            continue
    
    if remaining_fields and not APPLICATION_SETTINGS["headless_mode"]:
        print(f"INFO: Found {len(remaining_fields)} remaining required fields")
        response = input("Would you like to fill remaining fields manually? (y/n): ").strip().lower()
        
        if response == 'y':
            for i, field in enumerate(remaining_fields):
                try:
                    field_type = field.get_attribute('type') or 'text'
                    field_id = field.get_attribute('id') or ''
                    field_name = field.get_attribute('name') or ''
                    field_placeholder = field.get_attribute('placeholder') or ''
                    
                    print(f"\n--- Field {i+1} ---")
                    print(f"Type: {field.tag_name} ({field_type})")
                    print(f"ID: {field_id}")
                    print(f"Name: {field_name}")
                    print(f"Placeholder: {field_placeholder}")
                    
                    user_input = input("Enter value (or 'skip'): ").strip()
                    
                    if user_input.lower() != 'skip':
                        if field_type == 'file':
                            field.send_keys(os.path.abspath(user_input))
                            print(f"SUCCESS: Uploaded {user_input}")
                        elif field.tag_name == 'select':
                            select = Select(field)
                            select.select_by_visible_text(user_input)
                            print(f"SUCCESS: Selected {user_input}")
                        else:
                            field.clear()
                            field.send_keys(user_input)
                            print(f"SUCCESS: Filled with {user_input}")
                except Exception as e:
                    print(f"ERROR: Could not fill field: {str(e)}")
    
    return len(remaining_fields)

def submit_application(driver):
    """Submit the application."""
    print("INFO: Looking for submit button...")
    
    submit_selectors = [
        "//button[contains(translate(text(), 'SUBMIT', 'submit'), 'submit')]",
        "//button[contains(translate(text(), 'APPLY', 'apply'), 'apply')]",
        "//button[contains(text(), 'Submit Application')]",
        "//button[contains(text(), 'Apply')]",
        "//button[contains(text(), 'Submit')]",
        "//button[contains(text(), 'Continue')]",
        "//button[contains(text(), 'Next')]",
        "//button[contains(text(), 'Save')]",
        "//button[contains(text(), 'Save and Continue')]",
        "//button[contains(text(), 'Finish')]",
        "//input[@type='submit']",
        "//button[@type='submit']",
        "//button[contains(@class, 'submit')]",
        "//button[contains(@class, 'apply')]",
        "//button[contains(@class, 'continue')]",
        "//button[contains(@class, 'next')]",
        "//button[contains(@class, 'save')]",
        "//button[contains(@class, 'finish')]"
    ]
    
    for selector in submit_selectors:
        try:
            submit_btn = driver.find_element(By.XPATH, selector)
            if submit_btn.is_displayed() and submit_btn.is_enabled():
                print(f"INFO: Found submit button: {submit_btn.text}")
                
                if not APPLICATION_SETTINGS["headless_mode"]:
                    confirm = input("Submit application? (y/n): ").strip().lower()
                    if confirm != 'y':
                        print("Submission cancelled.")
                        return False
                
                submit_btn.click()
                print("SUCCESS: Application submitted!")
                time.sleep(5)
                return True
        except:
            continue
    
    # If no submit button found, look for any clickable buttons
    print("INFO: No standard submit button found, looking for any clickable buttons...")
    try:
        buttons = driver.find_elements(By.XPATH, "//button[not(@disabled)]")
        for button in buttons:
            if button.is_displayed() and button.is_enabled():
                button_text = button.text.strip().lower()
                if any(word in button_text for word in ['submit', 'apply', 'continue', 'next', 'save', 'finish']):
                    print(f"INFO: Found potential submit button: {button.text}")
                    
                    if not APPLICATION_SETTINGS["headless_mode"]:
                        confirm = input(f"Click '{button.text}'? (y/n): ").strip().lower()
                        if confirm != 'y':
                            continue
                    
                    button.click()
                    print("SUCCESS: Button clicked!")
                    time.sleep(5)
                    return True
    except:
        pass
    
    print("WARNING: Could not find submit button")
    return False

def click_add_buttons(driver):
    """Clicks 'Add' buttons for Experience and Education sections."""
    print("INFO: Clicking 'Add' buttons if available...")

    try:
        add_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Add') or contains(text(), 'Add Another')]")
        for btn in add_buttons:
            if btn.is_displayed():
                print(f"INFO: Clicking '{btn.text}'")
                btn.click()
                time.sleep(2)  # allow section to expand
    except Exception as e:
        print(f"WARNING: Could not click add buttons: {str(e)}")

def fill_experience_fields(driver):
    print("INFO: Filling Work Experience section...")
    try:
        driver.find_element(By.XPATH, "//input[contains(@name, 'jobTitle')]").send_keys("Intern")
        driver.find_element(By.XPATH, "//input[contains(@name, 'company')]").send_keys("RecommerceX")
        driver.find_element(By.XPATH, "//input[contains(@name, 'location')]").send_keys("Noida")
        driver.find_element(By.XPATH, "//textarea").send_keys("Developed an Application with Zoho ")
        
        # Calendar dropdown
        from_field = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'MM/YYYY')]")
        from_field.send_keys("052025")  # Example: June 2024
        to_field = driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'MM/YYYY')]")[1]
        to_field.send_keys("072025")

        print("SUCCESS: Work experience filled.")
    except Exception as e:
        print(f"WARNING: Could not fill experience: {str(e)}")

def fill_education_fields(driver):
    print("INFO: Filling Education section...")
    try:
        driver.find_element(By.XPATH, "//input[contains(@name, 'school')]") \
              .send_keys(PERSONAL_INFO["university_name"])

        select_degree = Select(driver.find_element(By.XPATH, "//select[contains(@name, 'degree')]"))
        select_degree.select_by_visible_text("Bachelor's Degree")

        driver.find_element(By.XPATH, "//input[contains(@name, 'fieldOfStudy')]").send_keys("Computer Science")

        from_input = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'YYYY')]")
        from_input.send_keys("2022")

        to_input = driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'YYYY')]")[1]
        to_input.send_keys("2026")

        print("SUCCESS: Education section filled.")
    except Exception as e:
        print(f"WARNING: Could not fill education: {str(e)}")

def upload_resume_and_links(driver):
    try:
        print("INFO: Uploading resume and LinkedIn...")
        # Resume
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(FILE_PATHS["resume_path"])
        print("SUCCESS: Resume uploaded")

        # LinkedIn
        linkedin_input = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'LinkedIn')]")
        linkedin_input.send_keys(PERSONAL_INFO["linkedin_url"])
        print("SUCCESS: LinkedIn URL entered")
    except Exception as e:
        print(f"WARNING: Could not upload resume or LinkedIn: {e}")


def click_add_buttons_if_needed(driver):
    print("INFO: Checking if 'Add' buttons are needed...")

    def field_exists(field_label):
        try:
            driver.find_element(By.XPATH, f"//*[contains(text(), '{field_label}')]")
            return True
        except:
            return False

    try:
        if not field_exists("Job Title"):
            exp_add_btns = driver.find_elements(By.XPATH, "//button[contains(@data-automation-id,'add-button')]")
            if exp_add_btns:
                driver.execute_script("arguments[0].scrollIntoView(true);", exp_add_btns[0])
                exp_add_btns[0].click()
                print("SUCCESS: Clicked 'Add' button for Experience")

        if not (field_exists("School") or field_exists("University")):
            edu_add_btns = driver.find_elements(By.XPATH, "//button[contains(@data-automation-id,'add-button')]")
            if len(edu_add_btns) > 1:
                driver.execute_script("arguments[0].scrollIntoView(true);", edu_add_btns[1])
                edu_add_btns[1].click()
                print("SUCCESS: Clicked 'Add' button for Education")

    except Exception as e:
        print(f"WARNING: Could not click add buttons: {e}")



def apply_to_job(driver, job_url):
    """Main job application logic."""
    print(f"\n--- Starting Application for: {job_url} ---")
    
    try:
        driver.get(job_url)
        time.sleep(5)

        print(f"INFO: Page title: {driver.title}")
        print(f"INFO: Current URL: {driver.current_url}")
        
        # Handle login if needed
        if not handle_login(driver):
            return False

        auto_select_radio_yes_no(driver)
        filled_count = find_and_fill_fields(driver)

        if filled_count > 0:
            print(f"INFO: Successfully filled {filled_count} fields")
        else:
            print("WARNING: No fields were filled automatically")

        handle_remaining_fields(driver)
        success = submit_application(driver)

        input("If this is a multi-step form, click 'Save and Continue'. Press Enter when next section is visible...")

        while success:
            print("INFO: Continuing to next section of the form...")
            
            filled_again = find_and_fill_fields(driver)
            handle_remaining_fields(driver)

            input("Press Enter once 'Add' buttons for Experience/Education are clickable...")

            click_add_buttons_if_needed(driver)
            fill_experience_fields(driver)
            fill_education_fields(driver)
            upload_resume_and_links(driver)

            success = submit_application(driver)

        return success

    except Exception as e:
        print(f"ERROR: Failed to apply to {job_url}: {str(e)}")
        return False


def main():
    """Main execution function."""
    job_urls_file = os.path.join(os.path.dirname(__file__), "job_urls.txt")
    
    try:
        with open(job_urls_file, "r") as f:
            job_application_urls = [url.strip() for url in f.readlines() if url.strip()]
    except FileNotFoundError:
        print("WARNING: job_urls.txt not found. Using default URL...")
        job_application_urls = ["https://cornerstone.csod.com/ux/ats/careersite/2/requisition/10494/application?c=cornerstone&source=LinkedIn&jobboardid=0#1"]
    
    if not job_application_urls:
        print("ERROR: No job URLs provided.")
        sys.exit(1)
    
    driver = None
    successful_applications = []
    failed_applications = []
    
    try:
        driver = initialize_driver(headless=APPLICATION_SETTINGS["headless_mode"])
        
        for url in job_application_urls:
            try:
                success = apply_to_job(driver, url)
                if success:
                    successful_applications.append(url)
                    print(f"SUCCESS: Applied to {url}")
                else:
                    failed_applications.append((url, "Application failed"))
                    print(f"FAILED: Could not apply to {url}")
                
                if url != job_application_urls[-1]:
                    time.sleep(APPLICATION_SETTINGS["pause_between_applications"])
                    
            except Exception as e:
                print(f"ERROR: Failed to process {url}: {str(e)}")
                failed_applications.append((url, str(e)))
                continue
                
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
    finally:
        if driver:
            driver.quit()
    
    # Summary
    print("\n=== Application Summary ===")
    print(f"Total URLs: {len(job_application_urls)}")
    print(f"Successful: {len(successful_applications)}")
    print(f"Failed: {len(failed_applications)}")
    
    if failed_applications:
        print("\nFailed Applications:")
        for url, reason in failed_applications:
            print(f"- {url}: {reason}")

if __name__ == "__main__":
    main() 