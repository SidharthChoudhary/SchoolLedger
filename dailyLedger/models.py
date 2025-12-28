from django.db import models


class IncomeManager(models.Manager):
    """Custom manager for Income to exclude payment_type field and include fees_account"""
    def get_queryset(self):
        return super().get_queryset().defer('payment_type').select_related('fees_account')


class LedgerEntryBase(models.Model):
    """Abstract base model for Expense and Income entries"""
    
    PAYMENT_TYPE_CHOICES = [
        ('Cash', 'Cash'),
        ('Credit', 'Credit'),
        ('Against Credit', 'Against Credit'),
    ]

    voucher_number = models.CharField(max_length=60, blank=True)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    details = models.CharField(max_length=200, blank=True)

    major_head = models.CharField(max_length=80, blank=True)
    head = models.CharField(max_length=80, blank=True)
    sub_head = models.CharField(max_length=80, blank=True, help_text='For salary: employee name. For others: vendor/account name.')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='Cash', blank=True, verbose_name='Transaction Type')
    session = models.ForeignKey('Session', null=True, blank=True, on_delete=models.SET_NULL)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.voucher_number} - {self.date} - {self.amount}"

    @property
    def account_name(self):
        """Get account name from sub_head"""
        return self.sub_head or "Unknown"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class Expense(LedgerEntryBase):
    """Expense ledger entries"""
    
    class Meta:
        ordering = ["-date", "-id"]
    
    def __str__(self):
        return f"Expense: {self.voucher_number} - {self.date} - {self.amount}"


class Income(LedgerEntryBase):
    """Income ledger entries"""
    fees_account = models.ForeignKey(
        'students.FeesAccount',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text='Link to fees account (for student fee income tracking)'
    )
    
    objects = IncomeManager()
    
    class Meta:
        ordering = ["-date", "-id"]
    
    def save(self, *args, **kwargs):
        """Auto-generate voucher number if not provided"""
        if not self.voucher_number or self.voucher_number.strip() == '':
            # Get the latest income record and extract number
            latest = Income.objects.filter(voucher_number__startswith='V').order_by('-id').first()
            if latest and latest.voucher_number:
                try:
                    # Extract number from voucher like "V1001"
                    num = int(latest.voucher_number[1:])
                    self.voucher_number = f'V{num + 1}'
                except (ValueError, IndexError):
                    self.voucher_number = 'V1001'
            else:
                self.voucher_number = 'V1001'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Income: {self.voucher_number} - {self.date} - {self.amount}"
class Head(models.Model):
    # Head_Id will be auto-created by Django as "id" (auto-increment)
    LEDGER_TYPE_CHOICES = [
        ('Expense', 'Expense'),
        ('Income', 'Income'),
    ]
    
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    
    major_head = models.CharField(max_length=80)
    head = models.CharField(max_length=80)
    sub_head = models.CharField(max_length=80, blank=True)
    details = models.TextField(blank=True, help_text='Additional details or notes for this head')
    ledger_type = models.CharField(max_length=10, choices=LEDGER_TYPE_CHOICES, default='Expense')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["major_head", "head", "sub_head"]
        unique_together = ("major_head", "head", "sub_head")  # optional but recommended

    def __str__(self):
        return f"{self.major_head} / {self.head} / {self.sub_head}"


class Session(models.Model):
    STATUS_CHOICES = [
        ("", "-- Select Status --"),
        ("next_session", "Next Session"),
        ("current_session", "Current Session"),
        ("old_session", "Old Session"),
    ]

    session = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-session"]

    def __str__(self):
        return f"{self.session} ({self.get_status_display()})"


class FeesStructure(models.Model):
    """Fees structure for different sessions and classes"""
    session = models.ForeignKey('Session', on_delete=models.CASCADE, related_name='fees_structures')
    class_code = models.ForeignKey('students.Class', on_delete=models.CASCADE, related_name='fees_structures')
    
    # Fees
    fee_tuition = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    fee_tc = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, verbose_name='Fee TC')
    fee_admission = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    
    # Books
    book_set = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    book_diary = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    book_other = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    
    # Uniform
    uniform_shirt = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    uniform_pant = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    uniform_tie = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    uniform_belt = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    uniform_id_card = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('session', 'class_code')
        ordering = ['-session', 'class_code']
    
    def __str__(self):
        return f"{self.session.session} - {self.class_code.class_code}"
