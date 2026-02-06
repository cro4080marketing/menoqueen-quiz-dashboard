#!/bin/bash

FILE="queens-cool-advertorial.html"

# Fix remaining surgeon references
sed -i '' 's/The HRT dependency surgeon? Wanted to slice her open for a <span data-cc-check-decimal="true" data-cc-price="65,000">\$65,000<\/span> procedure with a 35% failure rate and permanent disruption\./The hormone specialist? Wanted to put her on lifetime HRT with known cancer risks and weight gain side effects./g' "$FILE"

sed -i '' 's/I wasn'\''t going to let some surgeon use her as a Mercedes payment\./I wasn'\''t going to let some pharmaceutical company use her as a lifetime customer./g' "$FILE"

sed -i '' 's/Because the solution is too simple\. Too cheap\. And it would put half the body surgeons in Beverly Hills out of business\./Because the solution is too simple. Too cheap. And it would put half the hormone clinics out of business./g' "$FILE"

sed -i '' 's/But here'\''s what those surgeons didn'\''t count on\.\./But here'\''s what those pharmaceutical companies didn'\''t count on../g' "$FILE"

sed -i '' 's/THE RESULTS THAT HAVE SURGEONS SCRAMBLING/THE RESULTS THAT HAVE PHARMA COMPANIES SCRAMBLING/g' "$FILE"

sed -i '' 's/Because Dorothy was about to let some knife-happy surgeon replace her bodys at 71\./Because Dorothy was about to resign herself to a lifetime of synthetic hormones at 58./g' "$FILE"

echo "Final fixes done"
