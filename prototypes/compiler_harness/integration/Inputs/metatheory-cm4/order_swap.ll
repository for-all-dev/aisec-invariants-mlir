; MT-CM4 WITNESS SHAPE. Not a frozen artifact, not canonical Rev4 bitcode, and
; not an input to any model computation. It exists to make one countermodel
; mechanically checkable.
;
; Metatheory section 15, MT-CM4 refutes the invalid rule "equal payload,
; occurrence, and count for each static event template imply equal whole
; traces", using the two projected traces
;
;   rho_1 = [event_a(0), event_b(0)]
;   rho_2 = [event_b(0), event_a(0)]
;
; This module is that pair, with the choice between them made by a secret bit.
; Both arms write the SAME payload (0) to the SAME two public sinks; only the
; global order differs.
;
; Every template-local check passes: template `store to event_a` has payload 0,
; occurrence 1 and count 1 on both sides; likewise `store to event_b`. Only a
; whole-word, per-aligned-step comparison sees the difference.

define void @mt_cm4_order_selected(i8 %secret, ptr %event_a, ptr %event_b) {
entry:
  %bit = and i8 %secret, 1
  %high = icmp ne i8 %bit, 0
  br i1 %high, label %order_ab, label %order_ba

order_ab:
  store i8 0, ptr %event_a
  store i8 0, ptr %event_b
  br label %done

order_ba:
  store i8 0, ptr %event_b
  store i8 0, ptr %event_a
  br label %done

done:
  ret void
}
