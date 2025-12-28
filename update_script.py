with open(r'dailyLedger\templates\dailyLedger\expense_home.html', 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find('<script>')
end = content.find('</script>') + len('</script>')

new_script = '''<script>
			document.addEventListener('DOMContentLoaded', function() {
				const headData = {{ head_data_json|safe }};
				
				function setOptions(selectEl, data, emptyVal) {
					selectEl.innerHTML = '<option value="">' + emptyVal + '</option>';
					
					if (Array.isArray(data)) {
						data.forEach(item => {
							const opt = document.createElement('option');
							opt.value = item;
							opt.textContent = item;
							selectEl.appendChild(opt);
						});
					} else if (typeof data === 'object' && data !== null) {
						for (const [val] of Object.entries(data)) {
							const opt = document.createElement('option');
							opt.value = val;
							opt.textContent = val;
							selectEl.appendChild(opt);
						}
					}
				}

				// Handle filter form (method="get") for Search Transactions
				const filterForm = document.querySelector('form[method="get"]');
				if (filterForm) {
					const filterMajor = filterForm.querySelector('[name="major_head"]');
					const filterHead = filterForm.querySelector('[name="head"]');
					const filterSub = filterForm.querySelector('[name="sub_head"]');
					
					if (filterMajor && filterHead && filterSub) {
						filterMajor.addEventListener('change', function() {
							const major = this.value;
							filterHead.value = '';
							filterSub.innerHTML = '<option value="">All</option>';
							if (major && headData.Expense && headData.Expense[major]) {
								setOptions(filterHead, headData.Expense[major], 'All');
							} else {
								filterHead.innerHTML = '<option value="">All</option>';
							}
						});

						filterHead.addEventListener('change', function() {
							const major = filterMajor.value;
							const head = this.value;
							filterSub.value = '';
							if (major && head && headData.Expense && headData.Expense[major] && headData.Expense[major][head]) {
								setOptions(filterSub, headData.Expense[major][head], 'All');
							} else {
								filterSub.innerHTML = '<option value="">All</option>';
							}
						});
					}
				}

				// Handle entry form (method="post") for Add Expense
				const entryForm = document.querySelector('form[method="post"]');
				if (entryForm) {
					const majorSel = entryForm.querySelector('[name="major_head"]');
					const headSel = entryForm.querySelector('[name="head"]');
					const subSel = entryForm.querySelector('[name="sub_head"]');
					
					if (majorSel && headSel && subSel) {
						majorSel.addEventListener('change', function() {
							const major = this.value;
							headSel.value = '';
							subSel.innerHTML = '<option value="">-- Select --</option>';
							if (major && headData.Expense && headData.Expense[major]) {
								setOptions(headSel, headData.Expense[major], '-- Select --');
							} else {
								headSel.innerHTML = '<option value="">-- Select --</option>';
							}
						});

						headSel.addEventListener('change', function() {
							const major = majorSel.value;
							const head = this.value;
							subSel.value = '';
							if (major && head && headData.Expense && headData.Expense[major] && headData.Expense[major][head]) {
								setOptions(subSel, headData.Expense[major][head], '-- Select --');
							} else {
								subSel.innerHTML = '<option value="">-- Select --</option>';
							}
						});

						if (majorSel.value) {
							majorSel.dispatchEvent(new Event('change'));
						}
					}
				}
			});
		</script>'''

if start != -1 and end > start:
    new_content = content[:start] + new_script + content[end:]
    with open(r'dailyLedger\templates\dailyLedger\expense_home.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('SUCCESS: File updated')
else:
    print('ERROR: Script tag not found')
