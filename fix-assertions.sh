#!/bin/bash
# Fix <unrepresentable> tokens and empty static blocks in decompiled source

echo "Fixing assertion tokens in decompiled source..."

# Detect sed variant (BSD vs GNU)
if sed --version 2>/dev/null | grep -q GNU; then
    SED_INPLACE="sed -i"
else
    # BSD sed (macOS) requires empty string after -i
    SED_INPLACE="sed -i ''"
fi

# Find all Java files that need fixing
files=$(find decompiled -name "*.java" -type f)
count=0

for file in $files; do
    modified=false

    # Replace <unrepresentable> with AssertionHelper
    if grep -q "<unrepresentable>" "$file"; then
        $SED_INPLACE 's/<unrepresentable>/AssertionHelper/g' "$file"
        modified=true
    fi

    # Remove empty assertion static blocks
    if grep -q "static {" "$file"; then
        # Remove: static { if (AssertionHelper.$assertionsDisabled) { } }
        $SED_INPLACE '/static {/{N;/if (AssertionHelper\.\$assertionsDisabled) {/{N;/}/{N;/}/d;}}}' "$file"
        modified=true
    fi

    # Fix CODEC field initialization in interfaces
    if grep -q "BuilderCodecMapCodec<.*> CODEC;" "$file" && grep -q "CODEC = new BuilderCodecMapCodec<>" "$file"; then
        # This is a simplified fix - may need adjustment for complex cases
        initialization=$(grep -oP 'CODEC = \K.*(?=;)' "$file" 2>/dev/null | head -1)
        if [ -n "$initialization" ]; then
            $SED_INPLACE "s/\(BuilderCodecMapCodec<[^>]*> CODEC\);/\1 = $initialization;/" "$file"
            $SED_INPLACE '/static {/,/CODEC = new BuilderCodecMapCodec<>/d' "$file"
            modified=true
        fi
    fi

    if [ "$modified" = true ]; then
        echo "  Fixed: ${file#decompiled/}"
        ((count++))
    fi
done

echo ""
echo "Fixed $count files"
if [ $count -gt 0 ]; then
    echo "You can now run javadoc successfully!"
else
    echo "No files needed fixing."
fi
