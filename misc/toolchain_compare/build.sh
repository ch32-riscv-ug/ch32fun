#!/usr/bin/env bash
# Build every example of a ch32fun tree and record the ELF sizes.
#
# Usage: build.sh SRC NAME OUT [make args...]
#   SRC   ch32fun tree to build (may be another checkout than this script's)
#   NAME  configuration name written to the CSV
#   OUT   output directory: OUT/sizes.csv and OUT/logs/
#   SIZE  environment: the size tool (default riscv64-unknown-elf-size)
#
# Each example gets its own generated linker script so parallel builds do not
# overwrite one shared file.
set -u

src=$(cd "$1" && pwd); name=$2; out=$(mkdir -p "$3" && cd "$3" && pwd); shift 3
export SIZE=${SIZE:-riscv64-unknown-elf-size} NAME=$name OUT=$out
mkdir -p "$out/logs" "$out/rows"

one() {
	local dir=$1 t log
	shift
	t=$(basename "$dir")
	log="$OUT/logs/${dir//\//__}.log"
	if make -C "$dir" GENERATED_LD_FILE=generated.ld "$@" "$t.elf" >"$log" 2>&1 && [ -f "$dir/$t.elf" ]; then
		read -r text data bss _ < <("$SIZE" "$dir/$t.elf" | awk 'NR==2')
		echo "$NAME,$dir,ok,$text,$data,$bss" >"$OUT/rows/${dir//\//__}"
	else
		echo "$NAME,$dir,fail,,," >"$OUT/rows/${dir//\//__}"
	fi
}
export -f one

cd "$src"
find examples* -mindepth 2 -maxdepth 3 -name funconfig.h -printf '%h\n' | sort >"$out/list.txt"
echo "$(wc -l <"$out/list.txt") examples, make args: $*"
xargs -a "$out/list.txt" -P "$(nproc)" -I{} bash -c 'one "$@"' _ {} "$@"

{
	echo "config,example,status,text,data,bss"
	cat "$out"/rows/* | sort -t, -k2
} >"$out/sizes.csv"
rm -r "$out/rows"
echo "ok: $(grep -c ',ok,' "$out/sizes.csv")  fail: $(grep -c ',fail,' "$out/sizes.csv")"
grep ',fail,' "$out/sizes.csv" | cut -d, -f2 | sed 's/^/  failed: /'
exit 0
