from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.hashers import check_password
from django.contrib.auth import logout
from policy_assessment.models import User, Result, AcknowledgedPolicies
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.urls import reverse
import os
from django.contrib import messages
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from .utils import custom_token_generator
from urllib.parse import urljoin
from .utils import extract_questions_without_answers
import re
import random
import pdfplumber
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
            if check_password(password, user.password):
                request.session['user_id'] = user.email
                request.session['user_name'] = user.name
                request.session['role'] = user.role.strip().lower()

                if request.session['role'] == 'admin':
                    return redirect('welcome_admin')
                else:
                    return redirect('welcome_employee')
            else:
                return render(request, 'policy_assessment/login.html', {'error': 'Invalid credentials'})
        except User.DoesNotExist:
            return render(request, 'policy_assessment/login.html', {'error': 'Invalid credentials'})

    return render(request, 'policy_assessment/login.html')

# Role-Based Views

def welcome_admin(request):
    if not request.session.get('role'):
        return redirect('login')
    if request.session.get('role') != 'admin':
        return redirect('welcome_employee')

    # 1. Number of policies uploaded (excluding question PDFs)
    policy_dir = os.path.join(settings.MEDIA_ROOT, 'policy_documents')
    os.makedirs(policy_dir, exist_ok=True)
    file_list = os.listdir(policy_dir)
    policy_files = [f for f in file_list if not f.lower().endswith('questions.pdf')]
    num_policies_uploaded = len(policy_files)

    # 2. Number of employees who have acknowledged or taken a test
    employees_taken_test = Result.objects.values('email').distinct().count()
    employees_acknowledged = AcknowledgedPolicies.objects.values('user__email').distinct().count()
    employees_interacted = len(set(Result.objects.values_list('email', flat=True).distinct()).union(
        set(AcknowledgedPolicies.objects.values_list('user__email', flat=True).distinct())
    ))

    # 3. Number of employees pending to take a test
    total_employees = User.objects.filter(role='employee').count()
    employees_pending = total_employees - employees_interacted

    # 4. Average attempt count per policy
    policy_attempts = {}
    results = Result.objects.all()
    for result in results:
        policy = result.pdf_filename.strip().lower()
        if policy not in policy_attempts:
            policy_attempts[policy] = []
        policy_attempts[policy].append(result)

    avg_attempts_data = {}
    for policy, attempts in policy_attempts.items():
        attempt_count = len(attempts)
        num_employees = len(set([r.email.email for r in attempts]))
        avg_attempts = attempt_count / num_employees if num_employees > 0 else 0
        policy_name = attempts[0].pdf_filename if attempts else policy
        avg_attempts_data[policy_name] = round(avg_attempts, 2)

    bar_labels = list(avg_attempts_data.keys())
    bar_data = list(avg_attempts_data.values())

    # 5. Pie chart data: Policies Failed Till Last Attempt and Acknowledged vs Passed in Any Attempt and Acknowledged
    acknowledged_policies = set(AcknowledgedPolicies.objects.values_list('policy_name', flat=True).distinct())
    passed_policies = set(Result.objects.filter(result_percentage__gte=75).values_list('pdf_filename', flat=True).distinct())
    passed_and_acknowledged = passed_policies.intersection(acknowledged_policies)
    num_passed_and_acknowledged = len(passed_and_acknowledged)

    policy_user_attempts = {}
    for result in results:
        policy = result.pdf_filename.strip().lower()
        user = result.email.email
        if policy not in policy_user_attempts:
            policy_user_attempts[policy] = {}
        if user not in policy_user_attempts[policy]:
            policy_user_attempts[policy][user] = []
        policy_user_attempts[policy][user].append(result)

    MAX_ATTEMPTS = 4
    failed_till_last_and_acknowledged = set()
    for policy in acknowledged_policies:
        policy_lower = policy.strip().lower()
        if policy_lower in [p.strip().lower() for p in passed_policies]:
            continue
        if policy_lower in policy_user_attempts:
            for user, attempts in policy_user_attempts[policy_lower].items():
                if len(attempts) >= MAX_ATTEMPTS:
                    if all(result.result_percentage < 75 for result in attempts):
                        failed_till_last_and_acknowledged.add(policy)
                        break

    num_failed_till_last_and_acknowledged = len(failed_till_last_and_acknowledged)

    pie_data = [num_failed_till_last_and_acknowledged, num_passed_and_acknowledged]
    pie_labels = ['Failed Till Last Attempt and Acknowledged', 'Passed in Any Attempt and Acknowledged']

    return render(request, 'policy_assessment/welcome_admin.html', {
        'num_policies_uploaded': num_policies_uploaded,
        'employees_interacted': employees_interacted,
        'employees_pending': employees_pending,
        'employees_acknowledged': employees_acknowledged,
        'bar_labels': bar_labels,
        'bar_data': bar_data,
        'pie_labels': pie_labels,
        'pie_data': pie_data,
    })

def welcome_employee(request):
    if not request.session.get('role'):
        return redirect('login')
    if request.session.get('role') != 'employee':
        return redirect('welcome_admin')
    return render(request, 'policy_assessment/welcome_employee.html')

def logout_view(request):
    request.session.flush()
    return redirect('login')

# Employee Views

def previous_result(request):
    if request.session.get('role') != 'employee':
        return redirect('login')

    user_email = request.session.get('user_id')
    if not user_email:
        return redirect('login')

    try:
        user = User.objects.get(email=user_email)
    except User.DoesNotExist:
        return redirect('login')

    # Fetch all results for the user
    all_results = Result.objects.filter(email=user).order_by('-R_id')
    print(f"All results: {[{'R_id': r.R_id, 'pdf_filename': r.pdf_filename, 'result_percentage': r.result_percentage} for r in all_results]}")

    # Get the latest result from the session (if any)
    latest_result = request.session.get('latest_result')
    if latest_result:
        request.session.pop('latest_result', None)
        request.session.modified = True
        if all_results.exists():
            latest_policy = latest_result['pdf_filename'].strip().lower()
            latest_percentage = latest_result['percentage']
            # Exclude the latest result from past_results
            for result in all_results:
                if (result.pdf_filename.strip().lower() == latest_policy and
                        result.result_percentage == latest_percentage):
                    past_results = all_results.exclude(R_id=result.R_id)
                    break
        else:
            past_results = all_results
    else:
        past_results = all_results

    print(f"Raw past_results: {[{'R_id': r.R_id, 'pdf_filename': r.pdf_filename, 'result_percentage': r.result_percentage} for r in past_results]}")

    # Check if there are any results to display
    has_results = past_results.exists() or bool(latest_result)
    acknowledged_policies = AcknowledgedPolicies.objects.filter(user=user).values_list('policy_name', flat=True)

    # Calculate attempt counts, numbers, and pass status per policy
    attempt_counts = {}  # Total attempts per policy (actual)
    policy_pass_status = {}
    policy_results = {}
    policy_max_attempts = {}  # Track the highest attempt_number per policy
    max_attempts = 4  # Maximum possible attempts for display
    for result in all_results:
        policy = result.pdf_filename.strip().lower()
        if policy not in policy_results:
            policy_results[policy] = []
        policy_results[policy].append(result)

    for policy, results in policy_results.items():
        # Sort by R_id ascending so oldest attempt is 1st
        results.sort(key=lambda x: x.R_id)
        attempt_counts[policy] = len(results)
        policy_max_attempts[policy] = len(results)  # Since attempt_number is 1-based
        policy_pass_status[policy] = any(result.result_percentage >= 75 for result in results)

    print(f"Attempt counts (all results): {attempt_counts}")
    print(f"Policy max attempts: {policy_max_attempts}")
    print(f"Policy pass status: {policy_pass_status}")

    # Build enriched results for past_results
    enriched_results = []
    for result in past_results:
        policy = result.pdf_filename.strip().lower()
        attempt_number = next((i + 1 for i, r in enumerate(policy_results[policy]) if r.R_id == result.R_id), 0)
        total_attempts_for_policy = attempt_counts.get(policy, 0)
        print(f"Result R_id={result.R_id}, policy={policy}, attempt_number={attempt_number}, total_attempts={total_attempts_for_policy}")
        # Determine if this result should show the acknowledge button
        show_acknowledge = False
        if (attempt_number == policy_max_attempts.get(policy, 0) and  # This is the last attempt for the policy
            attempt_counts.get(policy, 0) >= max_attempts and  # Max attempts reached
            not policy_pass_status.get(policy, False) and  # No attempt passed
            result.pdf_filename not in acknowledged_policies):  # Policy not acknowledged
            show_acknowledge = True
        # If this attempt passed, always show the button (unless acknowledged)
        if result.result_percentage >= 75 and result.pdf_filename not in acknowledged_policies:
            show_acknowledge = True

        enriched_results.append({
            'pdf_filename': result.pdf_filename,
            'result_percentage': result.result_percentage,
            'status': 'Pass' if result.result_percentage >= 75 else 'Fail',
            'total_attempts': total_attempts_for_policy,  # Actual attempts for logic
            'display_total_attempts': max_attempts,  # Always 4 for display
            'attempt_number': attempt_number,
            'has_passed': policy_pass_status.get(policy, False),
            'show_acknowledge': show_acknowledge,
        })

    print(f"Enriched past_results: {enriched_results}")

    # Update latest_result with total_attempts and show_acknowledge
    if latest_result:
        policy = latest_result['pdf_filename'].strip().lower()
        total_attempts = attempt_counts.get(policy, 0)
        latest_result['total_attempts'] = total_attempts  # Actual attempts for logic
        latest_result['display_total_attempts'] = max_attempts  # Always 4 for display
        latest_result['has_passed'] = policy_pass_status.get(policy, False)
        # Determine if latest_result should show the acknowledge button
        show_acknowledge = False
        if (latest_result['status'] == "Pass" or
            (total_attempts >= max_attempts and not latest_result['has_passed']) and
            latest_result['pdf_filename'] not in acknowledged_policies):
            show_acknowledge = True
        latest_result['show_acknowledge'] = show_acknowledge
        # Add warning message if the acknowledge button is shown
        if show_acknowledge:
            latest_result['warning_message'] = "Please click Acknowledge to Accept the Policy"
        print(f"Latest result for {policy}: total_attempts={latest_result['total_attempts']}, display_total_attempts={latest_result['display_total_attempts']}, has_passed={latest_result['has_passed']}, show_acknowledge={show_acknowledge}, warning_message={latest_result.get('warning_message', 'None')}")

    return render(request, "policy_assessment/previous_result.html", {
        'latest_result': latest_result,
        'past_results': enriched_results,
        'has_results': has_results,
        'acknowledged_policies': acknowledged_policies,
        'max_attempts': max_attempts,
    })

# Admin Views

def view_acknowledgements(request):
    if request.session.get('role') != 'admin':
        return redirect('login')

    # Fetch all acknowledged policies
    acknowledged_policies = AcknowledgedPolicies.objects.all().select_related('user')

    # Prepare data with attempt counts
    acknowledgements = []
    for ack in acknowledged_policies:
        # Count the number of attempts for this user and policy
        attempt_count = Result.objects.filter(
            email=ack.user,
            pdf_filename=ack.policy_name
        ).count()
        
        acknowledgements.append({
            'employee_name': ack.user.name,
            'employee_email': ack.user.email,
            'policy_name': ack.policy_name,
            'attempt_count': attempt_count,
        })

    # Handle Excel download
    if 'download_excel' in request.GET:
        # Create an Excel workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Acknowledgements Report"

        # Define headers
        headers = ['Employee Name', 'Email', 'Policy Name', 'Attempts']
        ws.append(headers)

        # Apply bold font and center alignment to headers
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        # Add data rows
        for ack in acknowledgements:
            ws.append([
                ack['employee_name'],
                ack['employee_email'],
                ack['policy_name'],
                ack['attempt_count']
            ])

        # Adjust column widths for readability
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = max_length + 2
            ws.column_dimensions[column].width = adjusted_width

        # Save to BytesIO buffer
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        excel_data = buffer.getvalue()

        # Save the Excel file to the system
        reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        excel_path = os.path.join(reports_dir, 'acknowledgements_report.xlsx')
        with open(excel_path, 'wb') as f:
            f.write(excel_data)

        # Return the Excel file as a downloadable response
        response = HttpResponse(
            content=excel_data,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="acknowledgements_report.xlsx"'
        return response

    return render(request, "policy_assessment/view_acknowledgements.html", {
        'acknowledgements': acknowledgements
    })

def manage_tests(request):
    if request.session.get('role') != 'admin':
        return redirect('login')

    policy_dir = os.path.join(settings.MEDIA_ROOT, 'policy_documents')
    os.makedirs(policy_dir, exist_ok=True)

    if request.method == 'POST':
        uploaded_file = request.FILES.get('document')
        if uploaded_file and uploaded_file.content_type == 'application/pdf':
            filepath = os.path.join(policy_dir, uploaded_file.name)
            with open(filepath, 'wb+') as dest:
                for chunk in uploaded_file.chunks():
                    dest.write(chunk)
            messages.success(request, 'Question document uploaded successfully.')
        else:
            messages.error(request, 'Only PDF files are allowed.')

        return redirect('manage_tests')

    file_list = os.listdir(policy_dir)
    question_files = [f for f in file_list if f.lower().endswith('questions.pdf')]
    files = [{'name': name, 'url': f'/media/policy_documents/{name}'} for name in question_files]
    return render(request, 'policy_assessment/manage_tests.html', {'documents': files})

def delete_document(request, filename):
    if request.session.get('role') != 'admin':
        return redirect('login')
    
    file_path = os.path.join(settings.MEDIA_ROOT, 'policy_documents', filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        messages.success(request, f'Document {filename} deleted successfully.')
    else:
        messages.error(request, f'Document {filename} not found.')
    
    return redirect('manage_tests')

def view_results(request):
    if request.session.get('role') != 'admin':
        return redirect('login')

    results = Result.objects.all().order_by('-R_id')

    # Prepare data for the table and PDF
    results_data = []
    for result in results:
        status = 'Pass' if result.result_percentage >= 75 else 'Fail'
        results_data.append({
            'R_id': result.R_id,
            'email': result.email.email,
            'name': result.email.name,
            'pdf_filename': result.pdf_filename,
            'result_percentage': f"{result.result_percentage:.2f}%",
            'status': status,
        })

    # Handle PDF download
    if 'download_pdf' in request.GET:
        # Create a PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        # Define styles
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        title = Paragraph("Test Results Report", title_style)
        elements.append(title)

        # Define table data
        data = [['Test ID', 'Employee Email', 'Employee Name', 'Policy Document', 'Percentage', 'Status']]
        for result in results_data:
            data.append([
                str(result['R_id']),
                result['email'],
                result['name'],
                result['pdf_filename'],
                result['result_percentage'],
                result['status']
            ])

        # Create table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)

        # Build PDF
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()

        # Save the PDF to the system
        reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        pdf_path = os.path.join(reports_dir, 'test_results_report.pdf')
        with open(pdf_path, 'wb') as f:
            f.write(pdf)

        # Return the PDF as a downloadable response
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="test_results_report.pdf"'
        return response

    return render(request, "policy_assessment/view_results.html", {
        'results': results,
        'results_data': results_data,
    })

def delete_result(request, result_id):
    if request.method == 'POST':
        try:
            result = get_object_or_404(Result, R_id=result_id)
            result.delete()
            messages.success(request, f'Result with ID {result_id} deleted successfully.')
        except Result.DoesNotExist:
            messages.error(request, f'Result with ID {result_id} not found.')
    
    return redirect('view_results')

def manage_employees(request):
    if request.session.get('role') != 'admin':
        return redirect('login')

    message = ""
    error = ""

    if request.method == "POST":
        action = request.POST.get("action")
        email = request.POST.get("email")

        if action == "add":
            name = request.POST.get("name")
            password = request.POST.get("password")

            if User.objects.filter(email=email).exists():
                error = "User with this email already exists."
            else:
                User.objects.create(
                    email=email,
                    name=name,
                    role='employee',
                    password=make_password(password)
                )
                message = "Employee added successfully."

        elif action == "delete":
            try:
                user = User.objects.get(email=email)
                user.delete()
                message = "Employee deleted successfully."
            except User.DoesNotExist:
                error = "User does not exist."

    employees = User.objects.filter(role='employee')
    return render(request, "policy_assessment/manage_employees.html", {
        'employees': employees,
        'message': message,
        'error': error
    })

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            token = custom_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = request.build_absolute_uri(f"/reset-password/{uid}/{token}/")

            send_mail(
                "Password Reset Request",
                f"Click the link to reset your password: {reset_url}",
                "admin@example.com",
                [email],
                fail_silently=False,
            )

            return render(request, "policy_assessment/forgot_password.html", {"message": "Password reset email sent!"})

        except User.DoesNotExist:
            return render(request, "policy_assessment/forgot_password.html", {"error": "No user with that email found."})

    return render(request, "policy_assessment/forgot_password.html")

def reset_password(request, uidb64, token):
    try:
        email = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(email=email)

        if not custom_token_generator.check_token(user, token):
            messages.error(request, "The password reset link is invalid or expired.")
            return render(request, "policy_assessment/reset_password.html", {"valid": False})

        if request.method == "POST":
            new_password = request.POST.get("password")
            user.password = make_password(new_password)
            user.save()
            messages.success(request, "Your password has been reset successfully!")
            return redirect("login")

        return render(request, "policy_assessment/reset_password.html", {"valid": True})

    except (User.DoesNotExist, TypeError, ValueError, OverflowError):
        messages.error(request, "Invalid reset link.")
        return render(request, "policy_assessment/reset_password.html", {"valid": False})

def take_test(request):
    return render(request, "policy_assessment/instructions.html")

def extract_questions_without_answers(filepath):
    questions = []
    question_pattern = re.compile(
        r"(?:question[\.:]\s*|q\d+\.|^\d+\.\s*)(.*?)(?=(?:\(A\)|[A-D]\.|answer:))",
        re.DOTALL | re.IGNORECASE | re.MULTILINE
    )
    option_pattern = re.compile(
        r"\(([A-D])\)\s*([^()]+?)(?=\s*\(([A-D])\)|\s*answer:|\Z)",
        re.DOTALL | re.IGNORECASE
    )

    full_text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
                print(f"Extracting from page: {page.page_number}")
                print(f"Raw text:\n{text}\n{'-'*50}")
            else:
                print(f"No text extracted from page: {page.page_number}")

    if not full_text.strip():
        print("No text extracted from the entire PDF.")
        return questions

    print(f"Full concatenated text:\n{full_text}\n{'-'*50}")

    full_text = re.sub(r'\s+', ' ', full_text).strip()
    full_text = re.sub(r'\n+', '\n', full_text)

    question_matches = question_pattern.finditer(full_text)
    for q_match in question_matches:
        question_text = q_match.group(1).strip()
        question_text = re.sub(r'\s+', ' ', question_text)
        print(f"Found question: {question_text}")

        chunk = full_text[q_match.end():]
        next_question = question_pattern.search(chunk)
        if next_question:
            chunk = chunk[:next_question.start()]
        print(f"Chunk for options: {chunk}")

        option_matches = option_pattern.findall(chunk)
        print(f"Found options (raw matches): {option_matches}")

        if len(option_matches) >= 4:
            options = option_matches[:4]
            cleaned_options = []
            for label, text, _ in options:
                cleaned_text = re.sub(r'\s+', ' ', text).strip()
                full_option = f"({label}) {cleaned_text}"
                cleaned_options.append((f"({label})", cleaned_text))
                print(f"Option {label}: Raw Text='{text}', Cleaned Text='{cleaned_text}', Full Option='{full_option}'")

            questions.append({
                "question_text": question_text,
                "option_a": f"{cleaned_options[0][0]} {cleaned_options[0][1]}",
                "option_b": f"{cleaned_options[1][0]} {cleaned_options[1][1]}",
                "option_c": f"{cleaned_options[2][0]} {cleaned_options[2][1]}",
                "option_d": f"{cleaned_options[3][0]} {cleaned_options[3][1]}",
                "id": random.randint(1000, 9999)
            })
            print(f"Added question: {questions[-1]}")
        else:
            print(f"Warning: Only {len(option_matches)} options found for question: {question_text}")
            print(f"Chunk causing issue:\n{chunk}\n{'-'*50}")

    print(f"Questions extracted: {len(questions)}")
    return questions

def show_instructions(request, pdf_filename):
    return render(request, "policy_assessment/instructions.html", {
        "pdf_filename": pdf_filename
    })

def start_test(request):
    pdf_filename = request.GET.get('pdf')
    if not pdf_filename:
        return HttpResponse("No PDF selected.", status=400)

    user_email = request.session.get('user_id')
    if not user_email:
        return redirect('login')

    try:
        user = User.objects.get(email=user_email)
    except User.DoesNotExist:
        return HttpResponse("User not found.", status=404)

    # Normalize pdf_filename for consistent matching
    pdf_filename_normalized = pdf_filename.strip().lower()
    previous_attempts = Result.objects.filter(email=user, pdf_filename__iexact=pdf_filename_normalized).count()
    MAX_ATTEMPTS = 4
    current_attempt = previous_attempts + 1
    remaining_attempts = MAX_ATTEMPTS - current_attempt

    # Debug logging
    print(f"start_test: pdf_filename={pdf_filename}, normalized={pdf_filename_normalized}, previous_attempts={previous_attempts}, current_attempt={current_attempt}")

    if previous_attempts >= MAX_ATTEMPTS:
        passed_results = Result.objects.filter(email=user, pdf_filename__iexact=pdf_filename_normalized, result_percentage__gte=75)
        if passed_results.exists():
            return render(request, 'policy_assessment/instructions.html', {
                'pdf_filename': pdf_filename,
                'error': f'You have already passed the test for {pdf_filename}. No further attempts allowed.'
            })
        else:
            return render(request, 'policy_assessment/instructions.html', {
                'pdf_filename': pdf_filename,
                'error': f'You have reached the maximum number of attempts ({MAX_ATTEMPTS}) for {pdf_filename}.'
            })

    passed_results = Result.objects.filter(email=user, pdf_filename__iexact=pdf_filename_normalized, result_percentage__gte=75)
    if passed_results.exists():
        return render(request, 'policy_assessment/instructions.html', {
            'pdf_filename': pdf_filename,
            'error': f'You have already passed the test for {pdf_filename}. No further attempts allowed.'
        })

    base_name = os.path.splitext(pdf_filename)[0]
    questions_pdf_filename = f"{base_name} Questions.pdf"
    questions_pdf_path = os.path.join(settings.MEDIA_ROOT, 'policy_documents', questions_pdf_filename)
    print(f"Looking for questions PDF: {questions_pdf_path}")

    if not os.path.exists(questions_pdf_path):
        return HttpResponse(f"No questions PDF found for this policy. Expected: {questions_pdf_filename}", status=404)

    all_questions = extract_questions_without_answers(questions_pdf_path)
    if not all_questions:
        return HttpResponse("No questions extracted from the questions PDF.", status=400)

    answer_key = extract_answer_key(questions_pdf_path)
    if len(answer_key) < len(all_questions):
        return HttpResponse("Mismatch between questions and answers in the PDF.", status=400)

    for idx, question in enumerate(all_questions):
        if idx < len(answer_key):
            question['correct_answer'] = answer_key[idx]
        else:
            question['correct_answer'] = None
            print(f"Warning: No answer found for question {idx + 1}: {question['question_text']}")

    selected_questions = random.sample(all_questions, min(5, len(all_questions)))
    print(f"Selected questions with answers: {[{q['question_text']: q['correct_answer']} for q in selected_questions]}")

    request.session['selected_questions'] = selected_questions
    request.session.modified = True

    user_name = request.session.get('user_name', 'Guest')

    return render(request, 'policy_assessment/start_test.html', {
        'questions': selected_questions,
        'user_name': user_name,
        'pdf_filename': pdf_filename,
        'current_attempt': current_attempt,
        'remaining_attempts': remaining_attempts
    })

def extract_answer_key(filepath):
    answer_key = []
    full_text = ""
    with pdfplumber.open(filepath) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text:
                full_text += text + "\n"
                print(f"Page {page_num} text (full): {text}")
            else:
                print(f"No text extracted from page {page_num}")

    if not full_text:
        print("No text extracted from the entire PDF.")
        return answer_key

    print(f"Full text extracted:\n{full_text}\n{'-'*50}")

    question_pattern = re.compile(
        r"(?:question[\.:]\s*|q\d+\.|^\d+\.\s*)(.*?)(?=(?:question[\.:]\s*|q\d+\.|^\d+\.\s*|\Z))",
        re.DOTALL | re.IGNORECASE | re.MULTILINE
    )
    answer_patterns = [
        r"Answer:\s*\(([A-D])\)",
        r"Answer:\s+([A-D])\)",
        r"Answer:\s*([A-D])",
        r"Correct Answer:\s*\(([A-D])\)"
    ]

    question_matches = question_pattern.finditer(full_text)
    for idx, q_match in enumerate(question_matches):
        question_block = q_match.group(0).strip()
        print(f"Question {idx + 1} block:\n{question_block}\n{'-'*50}")

        answer_found = False
        for pattern in answer_patterns:
            answer_match = re.search(pattern, question_block, re.IGNORECASE)
            if answer_match:
                answer = answer_match.group(1).strip().upper()
                answer_key.append(answer)
                print(f"Question {idx + 1} answer: {answer}")
                answer_found = True
                break

        if not answer_found:
            print(f"No answer found for Question {idx + 1}. Block content:\n{question_block}\n{'-'*50}")

    if not answer_key:
        print("No answers found in the entire PDF. Possible issues:")
        print("- Check if 'Answer: (X)' or similar format exists in the PDF.")
        print("- Verify the exact text layout (e.g., spacing, case sensitivity).")
        print("- Ensure the PDF is the correct questions file.")
        print("Full text for manual inspection:")
        print(full_text[:1000])

    print(f"Final answer_key: {answer_key}")
    return answer_key

def submit_test(request):
    if request.method == "POST":
        pdf_filename = request.POST.get("pdf_filename")
        pdf_filename_normalized = pdf_filename.strip().lower()
        base_name = os.path.splitext(pdf_filename)[0]
        questions_pdf_filename = f"{base_name} Questions.pdf"
        questions_pdf_path = os.path.join(settings.MEDIA_ROOT, 'policy_documents', questions_pdf_filename)

        if not os.path.exists(questions_pdf_path):
            return HttpResponse(f"Questions PDF not found: {questions_pdf_filename}", status=404)

        selected_questions = request.session.get('selected_questions')
        if not selected_questions:
            return HttpResponse("Session expired or questions not found. Please restart the test.", status=400)

        total_questions = len(selected_questions)
        print(f"Selected questions for evaluation: {[{q['question_text']: q['correct_answer']} for q in selected_questions]}")

        correct_answers = 0
        total_score = 0
        incorrect_answers = []

        user_email = request.session.get('user_id')
        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            return HttpResponse("User not found.", status=404)

        previous_attempts = Result.objects.filter(email=user, pdf_filename__iexact=pdf_filename_normalized).count()
        MAX_ATTEMPTS = 4
        current_attempt = previous_attempts + 1
        print(f"submit_test: pdf_filename={pdf_filename}, normalized={pdf_filename_normalized}, previous_attempts={previous_attempts}, current_attempt={current_attempt}")

        for i in range(total_questions):
            selected_option = request.POST.get(f"question_{i}")
            correct_answer = selected_questions[i].get('correct_answer')
            print(f"Question {i + 1}: Selected option = {selected_option}, Correct answer = {correct_answer}")
            if selected_option and correct_answer:
                if selected_option.upper() == correct_answer:
                    correct_answers += 1
                    total_score += 4
                    print(f"Correct answer for question {i + 1}")
                else:
                    total_score -= 1
                    print(f"Wrong answer for question {i + 1}")
                    incorrect_answers.append({
                        'question_text': selected_questions[i]['question_text'],
                        'option_a': selected_questions[i]['option_a'],
                        'option_b': selected_questions[i]['option_b'],
                        'option_c': selected_questions[i]['option_c'],
                        'option_d': selected_questions[i]['option_d'],
                        'selected_option': f"({selected_option.upper()})",
                        'correct_answer': f"({correct_answer})"
                    })
            else:
                print(f"Missing selected option or correct answer for question {i + 1}")
                if selected_option:
                    incorrect_answers.append({
                        'question_text': selected_questions[i]['question_text'],
                        'option_a': selected_questions[i]['option_a'],
                        'option_b': selected_questions[i]['option_b'],
                        'option_c': selected_questions[i]['option_c'],
                        'option_d': selected_questions[i]['option_d'],
                        'selected_option': f"({selected_option.upper()})",
                        'correct_answer': "Unknown"
                    })

        max_score = total_questions * 4
        percentage = max(0, (total_score / max_score) * 100) if max_score > 0 else 0
        status = "Pass" if percentage >= 75 else "Fail"
        print(f"Total score: {total_score}, Percentage: {percentage}%, Status: {status}")

        if not user_email:
            return redirect('login')

        # Store the result with the original pdf_filename
        Result.objects.create(email=user, result_percentage=percentage, pdf_filename=pdf_filename)

        # Verify the number of results after saving
        total_results_after = Result.objects.filter(email=user, pdf_filename__iexact=pdf_filename_normalized).count()
        print(f"submit_test: After saving result, total results for {pdf_filename_normalized}: {total_results_after}")

        latest_result = {
            'pdf_filename': pdf_filename,
            'correct_answers': correct_answers,
            'total_questions': total_questions,
            'percentage': percentage,
            'status': status,
            'total_attempts': current_attempt,
        }

        if current_attempt == MAX_ATTEMPTS:
            latest_result['incorrect_answers'] = incorrect_answers
            print(f"Last attempt: incorrect_answers = {incorrect_answers}")

        request.session['latest_result'] = latest_result
        request.session.modified = True

        # Use the same styling as the acknowledgment email
        html_message = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Test Result</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    background: #ffffff;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                }}
                h2 {{
                    color: #1ba94c;
                    text-align: center;
                }}
                .result-block {{
                    padding: 20px;
                    background: #e0f7ef;
                    border-radius: 8px;
                    text-align: center;
                }}
                .result-block p {{
                    font-size: 16px;
                    margin: 10px 0;
                }}
                .result-status-pass {{
                    color: #28a745;
                    font-weight: bold;
                }}
                .result-status-fail {{
                    color: #dc3545;
                    font-weight: bold;
                }}
                .footer {{
                    margin-top: 20px;
                    text-align: center;
                    font-size: 14px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Your HR Policy Assessment Test Result</h2>
                <div class="result-block">
                    <p><strong>Policy:</strong> {pdf_filename}</p>
                    <p><strong>Correct Answers:</strong> {correct_answers} out of {total_questions}</p>
                    <p><strong>Percentage:</strong> {percentage:.2f}%</p>
                    <p><strong>Status:</strong> <span class="result-status-{status.lower()}">{status}</span></p>
                </div>
                <div class="footer">
                    <p>Thank you for completing the assessment!</p>
                    <p>Best regards,<br>Translab Technologies Pvt Ltd</p>
                </div>
            </div>
        </body>
        </html>
        """

        send_mail(
            subject='Your Test Result',
            message='Please view this email in an HTML-capable email client to see your test result.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )

        request.session.pop('selected_questions', None)
        request.session.modified = True

        return redirect('previous_result')

    return HttpResponse("Invalid request method.", status=400)

def acknowledge_policy(request, policy_name):
    if request.method == "POST":
        user_email = request.session.get('user_id')
        if not user_email:
            return redirect('login')

        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            return HttpResponse("User not found.", status=404)

        if AcknowledgedPolicies.objects.filter(user=user, policy_name=policy_name).exists():
            messages.info(request, f'You have already acknowledged the policy: {policy_name}.')
        else:
            AcknowledgedPolicies.objects.create(
                policy_name=policy_name,
                user=user
            )
            messages.success(request, f'Policy {policy_name} acknowledged successfully.')

            # Send acknowledgment confirmation email
            html_message = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Policy Acknowledgment Confirmation</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        background-color: #f4f4f4;
                        margin: 0;
                        padding: 0;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 20px auto;
                        background: #ffffff;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    }}
                    h2 {{
                        color: #1ba94c;
                        text-align: center;
                    }}
                    .result-block {{
                        padding: 20px;
                        background: #e0f7ef;
                        border-radius: 8px;
                        text-align: center;
                    }}
                    .result-block p {{
                        font-size: 16px;
                        margin: 10px 0;
                    }}
                    .result-status-pass {{
                        color: #28a745;
                        font-weight: bold;
                    }}
                    .footer {{
                        margin-top: 20px;
                        text-align: center;
                        font-size: 14px;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>Policy Acknowledgment Confirmation</h2>
                    <div class="result-block">
                        <p>You have successfully acknowledged the following policy:</p>
                        <p><strong>Policy:</strong> {policy_name}</p>
                        <p><strong>Status:</strong> <span class="result-status-pass">Acknowledged</span></p>
                    </div>
                    <div class="footer">
                        <p>Thank you for acknowledging the policy!</p>
                        <p>Best regards,<br>Translab Technologies Pvt Ltd</p>
                    </div>
                </div>
            </body>
            </html>
            """

            send_mail(
                subject='Policy Acknowledgment Confirmation',
                message='You have successfully acknowledged a policy. Please view this email in an HTML-capable email client to see the details.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user_email],
                html_message=html_message,
                fail_silently=False,
            )

        return redirect('previous_result')

    return HttpResponse("Invalid request method.", status=400)

PENDING_EMPLOYEES = [
    {'name': 'Parthana', 'email': 'prarthana.j@translab.io'},
    {'name': 'Jayesh', 'email': 'jayesh.d@translab.io'},
]

signer = TimestampSigner()

def send_invites(request):
    if request.method == 'POST':
        for employee in PENDING_EMPLOYEES:
            email = employee['email']
            name = employee['name']
            token = signer.sign(email)
            signup_url = request.build_absolute_uri(
                reverse('employee_signup') + f'?token={token}&name={name.replace(" ", "+")}'
            )
            subject = 'Complete Your Registration'
            message = f'Hi {name},\n\nPlease complete your signup by clicking this link:\n\n{signup_url}'
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
        return render(request, 'policy_assessment/manage_employees.html', {
            'message': 'Invitations sent successfully.'
        })

def employee_signup(request):
    if request.method == "POST":
        email = request.POST.get("email")
        name = request.POST.get("name")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        # Validate passwords match
        if password != confirm_password:
            return render(request, "policy_assessment/signup.html", {
                "error": "Passwords do not match."
            })

        # Check for existing email
        if User.objects.filter(email=email).exists():
            return render(request, "policy_assessment/signup.html", {
                "error": "An account with this email already exists."
            })

        # Create new user
        user = User(email=email, name=name, password=make_password(password), role='employee')
        user.save()

        messages.success(request, "Account created successfully! Please log in.")
        return redirect("login")

    return render(request, "policy_assessment/signup.html")

# Admin Uploads

def admin_policy_documents(request):
    if request.session.get('role') != 'admin':
        return redirect('login')

    policy_dir = os.path.join(settings.MEDIA_ROOT, 'policy_documents')
    os.makedirs(policy_dir, exist_ok=True)

    if request.method == 'POST':
        if 'document' in request.FILES:
            uploaded_file = request.FILES.get('document')
            if uploaded_file and uploaded_file.content_type == 'application/pdf':
                filepath = os.path.join(policy_dir, uploaded_file.name)
                with open(filepath, 'wb+') as dest:
                    for chunk in uploaded_file.chunks():
                        dest.write(chunk)
                messages.success(request, 'Policy document uploaded successfully.')
            else:
                messages.error(request, 'Only PDF files are allowed.')
        elif 'delete_file' in request.POST:
            filename = request.POST.get('delete_file')
            file_path = os.path.join(policy_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                messages.success(request, f'Document {filename} deleted successfully.')
            else:
                messages.error(request, f'Document {filename} not found.')

        return redirect('admin_policy_documents')

    file_list = os.listdir(policy_dir)
    files = [{'name': name, 'url': f'/media/policy_documents/{name}'} for name in file_list]
    return render(request, 'policy_assessment/policydocument.html', {'documents': files})

# Employee Views

def employee_policy_documents(request):
    if request.session.get('role') != 'employee':
        return redirect('login')

    policy_dir = os.path.join(settings.MEDIA_ROOT, 'policy_documents')
    file_list = os.listdir(policy_dir)
    policy_files = [f for f in file_list if not f.lower().endswith('questions.pdf')]
    documents = [{'name': name, 'url': f'/media/policy_documents/{name}'} for name in policy_files]
    return render(request, 'policy_assessment/policy.html', {'documents': documents})

def view_policy(request, filename):
    file_url = f"{settings.MEDIA_URL}policy_documents/{filename}"
    full_file_url = request.build_absolute_uri(file_url)
    user_role = request.session.get('role', '')

    # Check if the user should be prevented from retaking the test
    user_email = request.session.get('user_id')
    has_taken_test = False
    if user_email and user_role == 'employee':
        try:
            user = User.objects.get(email=user_email)
            # Check if the user has passed the test
            passed_results = Result.objects.filter(email=user, pdf_filename=filename, result_percentage__gte=75)
            if passed_results.exists():
                has_taken_test = True
            else:
                # If the user hasn't passed, check if they've reached the maximum attempts
                previous_attempts = Result.objects.filter(email=user, pdf_filename=filename).count()
                MAX_ATTEMPTS = 4
                if previous_attempts >= MAX_ATTEMPTS:
                    has_taken_test = True
        except User.DoesNotExist:
            pass

    return render(request, 'policy_assessment/view_policy.html', {
        'filename': filename,
        'file_url': file_url,
        'full_file_url': full_file_url,
        'user_role': user_role,
        'has_taken_test': has_taken_test
    })

def acknowledge_and_start_test(request, filename):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        if not user_id:
            return redirect('login')

        try:
            user = User.objects.get(email=user_id)
        except User.DoesNotExist:
            return HttpResponse("User not found.", status=404)

        # Check if the user should be prevented from retaking the test
        passed_results = Result.objects.filter(email=user, pdf_filename=filename, result_percentage__gte=75)
        previous_attempts = Result.objects.filter(email=user, pdf_filename=filename).count()
        MAX_ATTEMPTS = 4

        if passed_results.exists() or previous_attempts >= MAX_ATTEMPTS:
            # Redirect back to view_policy with an error message
            messages.error(request, f'You have already appeared for the test for {filename}.')
            return redirect('view_policy', filename=filename)

        # If the user hasn't passed and hasn't reached the maximum attempts, proceed to instructions
        return render(request, "policy_assessment/instructions.html", {
            "pdf_filename": filename
        })

    return redirect('view_policy', filename=filename)