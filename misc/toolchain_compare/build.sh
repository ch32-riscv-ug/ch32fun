#!/usr/bin/env bash
# Build every example of a ch32fun tree and record the ELF sizes.
#
# Usage: build.sh SRC NAME OUT [make args...]
#   SRC   ch32fun tree to build (may be another checkout than this script's)
#   NAME  configuration name written to the CSV
#   OUT   output directory: OUT/sizes.csv and OUT/logs/
#   SIZE / OBJCOPY / NM  environment: the tools (default riscv64-unknown-elf-*)
#
# flash is the size of the image written to flash (objcopy -O binary without
# .storage, as ch32fun.mk makes it), gaps between sections included. ram is
# _ebss - _data_vma plus the CH5xx highcode copied to RAM. text/data/bss are
# size(1)'s, for reference only: GNU size and llvm-size sort sections into
# them differently.
#
# Each example gets its own generated linker script so parallel builds do not
# overwrite one shared file.
set -u

src=$(cd "$1" && pwd); name=$2; out=$(mkdir -p "$3" && cd "$3" && pwd); shift 3
export SIZE=${SIZE:-riscv64-unknown-elf-size} OBJCOPY=${OBJCOPY:-riscv64-unknown-elf-objcopy} NM=${NM:-riscv64-unknown-elf-nm}
export NAME=$name OUT=$out
mkdir -p "$out/logs" "$out/rows"

sym() { # sym ELF NAME: the symbol's value in decimal, 0 if there is none
	local v
	v=$("$NM" "$1" | awk -v n="$2" '$3 == n { print $1; exit }')
	echo $((16#${v:-0}))
}
export -f sym

one() {
	local dir=$1 t log elf key flash ram
	shift
	t=$(basename "$dir")
	log="$OUT/logs/${dir//\//__}.log"
	if make -C "$dir" GENERATED_LD_FILE=generated.ld "$@" "$t.elf" >"$log" 2>&1 && [ -f "$dir/$t.elf" ]; then
		elf=$dir/$t.elf key=${dir//\//__}
		read -r text data bss _ < <("$SIZE" "$elf" | awk 'NR==2')
		"$OBJCOPY" -R .storage -O binary "$elf" "$OUT/$key.bin"
		flash=$(wc -c <"$OUT/$key.bin")
		rm -f "$OUT/$key.bin"
		ram=$(( $(sym "$elf" _ebss) - $(sym "$elf" _data_vma) + $(sym "$elf" _highcode_vma_end) - $(sym "$elf" _highcode_vma_start) ))
		echo "$NAME,$dir,ok,$flash,$ram,$text,$data,$bss" >"$OUT/rows/$key"
	else
		echo "$NAME,$dir,fail,,,,," >"$OUT/rows/${dir//\//__}"
	fi
}
export -f one

cd "$src"
find examples* -mindepth 2 -maxdepth 3 -name funconfig.h -printf '%h\n' | sort >"$out/list.txt"
echo "$(wc -l <"$out/list.txt") examples, make args: $*"
xargs -a "$out/list.txt" -P "$(nproc)" -I{} bash -c 'one "$@"' _ {} "$@"

{
	echo "config,example,status,flash,ram,text,data,bss"
	cat "$out"/rows/* | sort -t, -k2
} >"$out/sizes.csv"
rm -r "$out/rows"
echo "ok: $(grep -c ',ok,' "$out/sizes.csv")  fail: $(grep -c ',fail,' "$out/sizes.csv")"
grep ',fail,' "$out/sizes.csv" | cut -d, -f2 | sed 's/^/  failed: /'
exit 0
