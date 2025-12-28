from django.db import models


class Class(models.Model):
    """Store school classes/grades"""
    class_name = models.CharField(max_length=100, unique=True)
    class_code = models.CharField(max_length=5, unique=True, blank=True, null=True)
    age = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['age']
        verbose_name_plural = "Classes"
    
    def __str__(self):
        return f"{self.class_code}"


class Student(models.Model):
    CLASS_CHOICES = [
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, '5'),
        (6, '6'),
        (7, '7'),
        (8, '8'),
        (9, '9'),
        (10, '10'),
        (11, '11'),
        (12, '12'),
    ]
    
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('3rd_gender', '3rd Gender'),
    ]
    
    # Personal Details
    first_name = models.CharField(max_length=100, default='')
    last_name = models.CharField(max_length=100, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    fathers_name = models.CharField(max_length=200)
    mothers_name = models.CharField(max_length=200)
    gardians_name = models.CharField(max_length=200, blank=True, null=True)
    medical_conditions = models.TextField(blank=True, null=True)
    dietary_restrictions = models.TextField(blank=True, null=True)
    fathers_phone = models.CharField(max_length=20, blank=True, null=True)
    mothers_phone = models.CharField(max_length=20, blank=True, null=True)
    gardians_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Academic Details
    student_class = models.ForeignKey('Class', on_delete=models.SET_NULL, null=True, related_name='students_in_class')
    transport_method = models.BooleanField(default=False, verbose_name='Uses School Bus')
    previous_school = models.CharField(max_length=200, blank=True, null=True)
    srn = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name='Student Registration Number')
    rte = models.BooleanField(default=False, verbose_name='Right to Education')
    primary_account_holder = models.BooleanField(default=False, verbose_name='Primary Account Holder')
    admission_date = models.DateField(blank=True, null=True, verbose_name='Admission Date')
    fees_account = models.ForeignKey('FeesAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    session = models.ForeignKey('dailyLedger.Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    
    # Photo
    image = models.ImageField(upload_to='students/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['student_class__age', 'first_name', 'last_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def name(self):
        """Return full name for backward compatibility"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def fee_account_name(self):
        """Auto-generate fee account name if primary account holder"""
        if self.primary_account_holder and self.fees_account:
            # Format: (Account ID)-(Last Name)_(First Name)-SRN
            return f"{self.fees_account.account_id}-{self.last_name}_{self.first_name}-{self.srn}"
        return None


class StudentAccount(models.Model):
    """Track fees and charges for each student per session"""
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='accounts')
    session = models.ForeignKey('dailyLedger.Session', on_delete=models.CASCADE)
    
    # Fees fields
    tuition_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tc_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    book_diary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    book_other = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    admission_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    uniform_shirt = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    uniform_pant = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    uniform_tie = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    uniform_belt = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    uniform_id_card = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'session']
        ordering = ['-session', 'student__first_name']
    
    def __str__(self):
        return f"{self.student.name} - {self.session.session}"
    
    @property
    def total_fees(self):
        """Calculate total fees"""
        return (self.tuition_fees + self.tc_fees + self.book_diary + self.book_other +
                self.admission_fees + self.uniform_shirt + self.uniform_pant + 
                self.uniform_tie + self.uniform_belt + self.uniform_id_card)


class FeesAccount(models.Model):
    """Manage student fees accounts"""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]
    
    account_id = models.CharField(max_length=10, unique=True, editable=False)
    name = models.CharField(max_length=100, default='Unnamed Account')
    account_open = models.DateField()
    account_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    account_close = models.DateField(null=True, blank=True)
    register_page = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Fees Accounts"
    
    def __str__(self):
        return f"{self.account_id} - {self.name}"
    
    @property
    def account_name(self):
        """Alias for 'name' field for consistency with other models"""
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.account_id:
            # Get the next ID number
            last_account = FeesAccount.objects.all().order_by('id').last()
            if last_account:
                last_id = int(last_account.account_id)
                next_id = last_id + 1
            else:
                next_id = 1
            self.account_id = str(next_id).zfill(3)
        super().save(*args, **kwargs)


class SessionClassStudentMap(models.Model):
    """Master table mapping students to sessions and classes"""
    session = models.ForeignKey('dailyLedger.Session', on_delete=models.CASCADE, related_name='class_student_maps')
    student_class = models.ForeignKey('Class', on_delete=models.CASCADE, related_name='session_student_maps')
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='session_class_maps')
    srn = models.CharField(max_length=50, blank=True, null=True, verbose_name='Student Registration Number')
    promoted_date = models.DateTimeField(null=True, blank=True, verbose_name='Promotion Date')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['session', 'student_class', 'student']
        ordering = ['session', 'student_class__age', 'student__first_name']
        verbose_name_plural = "Session Class Student Maps"
    
    def __str__(self):
        return f"{self.student.first_name} {self.student.last_name} - {self.session.session} - {self.student_class.class_code}"
    
    def save(self, *args, **kwargs):
        # Auto-populate SRN from student
        if not self.srn and self.student:
            self.srn = self.student.srn
        super().save(*args, **kwargs)


class StudentAttendance(models.Model):
    """Track daily attendance for students"""
    ATTENDANCE_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
    ]

    session = models.ForeignKey('dailyLedger.Session', on_delete=models.CASCADE, related_name='student_attendance')
    student_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='attendance_records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    attendance = models.CharField(max_length=10, choices=ATTENDANCE_CHOICES, default='present')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['session', 'student', 'date']
        ordering = ['-date', 'student__first_name', 'student__last_name']

    def __str__(self):
        return f"{self.student.name} - {self.student_class.class_code} - {self.date} ({self.attendance})"
