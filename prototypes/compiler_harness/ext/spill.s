	.section	__TEXT,__text,regular,pure_instructions
	.build_version macos, 16, 0	sdk_version 26, 5
	.globl	_crypt_region                   ; -- Begin function crypt_region
	.p2align	6
_crypt_region:                          ; @crypt_region
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #176
	stp	x28, x27, [sp, #80]             ; 16-byte Folded Spill
	stp	x26, x25, [sp, #96]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #112]            ; 16-byte Folded Spill
	stp	x22, x21, [sp, #128]            ; 16-byte Folded Spill
	stp	x20, x19, [sp, #144]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #160]            ; 16-byte Folded Spill
	add	x29, sp, #160
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	.cfi_offset w27, -88
	.cfi_offset w28, -96
	str	x0, [sp, #8]                    ; 8-byte Folded Spill
	ldp	x11, x27, [x1]
	ldp	x28, x19, [x1, #16]
	ldp	x21, x20, [x1, #32]
	ldp	x22, x24, [x1, #48]
	ldp	x23, x8, [x1, #64]
	ldp	x26, x10, [x1, #80]
	ldp	x9, x12, [x1, #96]
	ldp	x13, x0, [x1, #112]
	stp	x13, x9, [sp, #64]              ; 16-byte Folded Spill
	stp	x23, x12, [sp, #48]             ; 16-byte Folded Spill
	str	x10, [sp, #40]                  ; 8-byte Folded Spill
	cbz	w2, LBB0_3
; %bb.1:
	mov	x25, #0                         ; =0x0
	mov	w14, w2
	str	x14, [sp, #16]                  ; 8-byte Folded Spill
	mov	x23, x8
LBB0_2:                                 ; =>This Inner Loop Header: Depth=1
	str	x0, [sp, #32]                   ; 8-byte Folded Spill
	eor	x0, x11, x25
	bl	_opaque
	str	x0, [sp, #24]                   ; 8-byte Folded Spill
	add	x0, x0, x27
	bl	_opaque
	mov	x27, x0
	eor	x0, x0, x28
	bl	_opaque
	mov	x28, x0
	add	x0, x0, x19
	bl	_opaque
	mov	x19, x0
	eor	x0, x0, x21
	bl	_opaque
	mov	x21, x0
	add	x0, x0, x20
	bl	_opaque
	mov	x20, x0
	eor	x0, x0, x22
	bl	_opaque
	mov	x22, x0
	add	x0, x0, x24
	bl	_opaque
	mov	x24, x0
	ldr	x8, [sp, #48]                   ; 8-byte Folded Reload
	eor	x0, x0, x8
	bl	_opaque
	str	x0, [sp, #48]                   ; 8-byte Folded Spill
	add	x0, x0, x23
	bl	_opaque
	mov	x23, x0
	eor	x0, x0, x26
	bl	_opaque
	mov	x26, x0
	ldr	x8, [sp, #40]                   ; 8-byte Folded Reload
	add	x0, x0, x8
	bl	_opaque
	ldr	x8, [sp, #72]                   ; 8-byte Folded Reload
	str	x0, [sp, #40]                   ; 8-byte Folded Spill
	eor	x0, x0, x8
	bl	_opaque
	str	x0, [sp, #72]                   ; 8-byte Folded Spill
	ldr	x8, [sp, #56]                   ; 8-byte Folded Reload
	add	x0, x0, x8
	bl	_opaque
	ldr	x8, [sp, #64]                   ; 8-byte Folded Reload
	str	x0, [sp, #56]                   ; 8-byte Folded Spill
	eor	x0, x0, x8
	bl	_opaque
	str	x0, [sp, #64]                   ; 8-byte Folded Spill
	ldr	x8, [sp, #32]                   ; 8-byte Folded Reload
	add	x0, x0, x8
	bl	_opaque
	ldp	x8, x11, [sp, #16]              ; 16-byte Folded Reload
	add	x25, x25, #1
	cmp	x8, x25
	b.ne	LBB0_2
	b	LBB0_4
LBB0_3:
	mov	x23, x8
LBB0_4:
	mov	x8, #0                          ; =0x0
	eor	x9, x27, x19
	eor	x10, x28, x21
	eor	x9, x10, x9
	eor	x10, x20, x22
	eor	x10, x10, x24
	eor	x9, x9, x10
	ldp	x12, x10, [sp, #40]             ; 16-byte Folded Reload
	eor	x10, x10, x23
	eor	x10, x10, x26
	eor	x10, x10, x12
	eor	x9, x9, x10
	ldr	x10, [sp, #72]                  ; 8-byte Folded Reload
	ldr	x12, [sp, #56]                  ; 8-byte Folded Reload
	eor	x10, x10, x12
	ldr	x12, [sp, #64]                  ; 8-byte Folded Reload
	eor	x10, x10, x12
	eor	x10, x10, x0
	eor	x10, x10, x11
	eor	x9, x9, x10
	ldr	x10, [sp, #8]                   ; 8-byte Folded Reload
	add	x0, x9, x10, lsr #60
	; InlineAsm Start
	; InlineAsm End
	ldp	x29, x30, [sp, #160]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #144]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #128]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #112]            ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #96]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #80]             ; 16-byte Folded Reload
	add	sp, sp, #176
	ret
	.cfi_endproc
                                        ; -- End function
	.section	__TEXT,__literal16,16byte_literals
	.p2align	4, 0x0                          ; -- Begin function main
lCPI1_0:
	.quad	4096                            ; 0x1000
	.quad	4097                            ; 0x1001
lCPI1_1:
	.quad	4098                            ; 0x1002
	.quad	4099                            ; 0x1003
lCPI1_2:
	.quad	4100                            ; 0x1004
	.quad	4101                            ; 0x1005
lCPI1_3:
	.quad	4102                            ; 0x1006
	.quad	4103                            ; 0x1007
lCPI1_4:
	.quad	4104                            ; 0x1008
	.quad	4105                            ; 0x1009
lCPI1_5:
	.quad	4106                            ; 0x100a
	.quad	4107                            ; 0x100b
lCPI1_6:
	.quad	4108                            ; 0x100c
	.quad	4109                            ; 0x100d
lCPI1_7:
	.quad	4110                            ; 0x100e
	.quad	4111                            ; 0x100f
	.section	__TEXT,__text,regular,pure_instructions
	.globl	_main
	.p2align	2
_main:                                  ; @main
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #192
	stp	x20, x19, [sp, #160]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #176]            ; 16-byte Folded Spill
	add	x29, sp, #176
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
Lloh0:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh1:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh2:
	ldr	x8, [x8]
	stur	x8, [x29, #-24]
Lloh3:
	adrp	x8, lCPI1_0@PAGE
Lloh4:
	ldr	q0, [x8, lCPI1_0@PAGEOFF]
Lloh5:
	adrp	x8, lCPI1_1@PAGE
Lloh6:
	ldr	q1, [x8, lCPI1_1@PAGEOFF]
	stp	q0, q1, [sp, #16]
Lloh7:
	adrp	x8, lCPI1_2@PAGE
Lloh8:
	ldr	q0, [x8, lCPI1_2@PAGEOFF]
Lloh9:
	adrp	x8, lCPI1_3@PAGE
Lloh10:
	ldr	q1, [x8, lCPI1_3@PAGEOFF]
	stp	q0, q1, [sp, #48]
Lloh11:
	adrp	x8, lCPI1_4@PAGE
Lloh12:
	ldr	q0, [x8, lCPI1_4@PAGEOFF]
Lloh13:
	adrp	x8, lCPI1_5@PAGE
Lloh14:
	ldr	q1, [x8, lCPI1_5@PAGEOFF]
	stp	q0, q1, [sp, #80]
Lloh15:
	adrp	x8, lCPI1_6@PAGE
Lloh16:
	ldr	q0, [x8, lCPI1_6@PAGEOFF]
Lloh17:
	adrp	x8, lCPI1_7@PAGE
Lloh18:
	ldr	q1, [x8, lCPI1_7@PAGEOFF]
	stp	q0, q1, [sp, #112]
	add	x1, sp, #16
	mov	x0, #61453                      ; =0xf00d
	movk	x0, #56237, lsl #16
	movk	x0, #60941, lsl #32
	movk	x0, #49407, lsl #48
	mov	w2, #3                          ; =0x3
	bl	_crypt_region
	mov	x19, x0
	bl	_sink
	bl	_probe_residue
                                        ; kill: def $w0 killed $w0 def $x0
	stp	x19, x0, [sp]
Lloh19:
	adrp	x0, l_.str@PAGE
Lloh20:
	add	x0, x0, l_.str@PAGEOFF
	bl	_printf
	ldur	x8, [x29, #-24]
Lloh21:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh22:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh23:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB1_2
; %bb.1:
	mov	w0, #0                          ; =0x0
	ldp	x29, x30, [sp, #176]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #160]            ; 16-byte Folded Reload
	add	sp, sp, #192
	ret
LBB1_2:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh21, Lloh22, Lloh23
	.loh AdrpAdd	Lloh19, Lloh20
	.loh AdrpLdr	Lloh17, Lloh18
	.loh AdrpAdrp	Lloh15, Lloh17
	.loh AdrpLdr	Lloh15, Lloh16
	.loh AdrpAdrp	Lloh13, Lloh15
	.loh AdrpLdr	Lloh13, Lloh14
	.loh AdrpAdrp	Lloh11, Lloh13
	.loh AdrpLdr	Lloh11, Lloh12
	.loh AdrpAdrp	Lloh9, Lloh11
	.loh AdrpLdr	Lloh9, Lloh10
	.loh AdrpAdrp	Lloh7, Lloh9
	.loh AdrpLdr	Lloh7, Lloh8
	.loh AdrpAdrp	Lloh5, Lloh7
	.loh AdrpLdr	Lloh5, Lloh6
	.loh AdrpAdrp	Lloh3, Lloh5
	.loh AdrpLdr	Lloh3, Lloh4
	.loh AdrpLdrGotLdr	Lloh0, Lloh1, Lloh2
	.cfi_endproc
                                        ; -- End function
	.p2align	6                               ; -- Begin function probe_residue
_probe_residue:                         ; @probe_residue
	.cfi_startproc
; %bb.0:
	stp	x28, x27, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	sub	sp, sp, #1, lsl #12             ; =4096
	sub	sp, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w27, -24
	.cfi_offset w28, -32
	mov	x8, #0                          ; =0x0
	mov	w0, #0                          ; =0x0
Lloh24:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh25:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh26:
	ldr	x9, [x9]
	stur	x9, [x29, #-24]
	add	x9, sp, #8
	mov	x10, #61453                     ; =0xf00d
	movk	x10, #56237, lsl #16
	movk	x10, #60941, lsl #32
	movk	x10, #49407, lsl #48
LBB2_1:                                 ; =>This Inner Loop Header: Depth=1
	ldr	x11, [x9, x8]
	cmp	x11, x10
	cinc	w0, w0, eq
	add	x8, x8, #8
	cmp	x8, #1, lsl #12                 ; =4096
	b.ne	LBB2_1
; %bb.2:
	ldur	x8, [x29, #-24]
Lloh27:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh28:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh29:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB2_4
; %bb.3:
	add	sp, sp, #1, lsl #12             ; =4096
	add	sp, sp, #16
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp], #32             ; 16-byte Folded Reload
	ret
LBB2_4:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh24, Lloh25, Lloh26
	.loh AdrpLdrGotLdr	Lloh27, Lloh28, Lloh29
	.cfi_endproc
                                        ; -- End function
	.section	__TEXT,__cstring,cstring_literals
l_.str:                                 ; @.str
	.asciz	"result=%llu  SECRET residue in freed frame = %u occurrence(s)\n"

.subsections_via_symbols
