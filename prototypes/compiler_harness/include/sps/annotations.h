#ifndef SPS_SOURCE_ANNOTATIONS_H
#define SPS_SOURCE_ANNOTATIONS_H

/*
 * SPS source annotations are locator metadata for a Clang AST extractor.
 * They do not change C/C++ types, the ABI, or the security policy.
 */
#if defined(SPS_EXTRACT_ANNOTATIONS)
#  if !defined(__clang__)
#    error "SPS_EXTRACT_ANNOTATIONS requires Clang"
#    define SPS_DETAIL_ANNOTATE(prefix, id)
#  elif !defined(__has_attribute)
#    error "SPS_EXTRACT_ANNOTATIONS requires Clang attribute detection"
#    define SPS_DETAIL_ANNOTATE(prefix, id)
#  elif !__has_attribute(annotate)
#    error "SPS_EXTRACT_ANNOTATIONS requires Clang annotate attributes"
#    define SPS_DETAIL_ANNOTATE(prefix, id)
#  else
#    define SPS_DETAIL_ANNOTATE(prefix, id) __attribute__((annotate(prefix id)))
#  endif
#else
#  define SPS_DETAIL_ANNOTATE(prefix, id)
#endif

#define SPS_ENTRY(id) SPS_DETAIL_ANNOTATE("sps.entry=", id)
#define SPS_HELPER(id) SPS_DETAIL_ANNOTATE("sps.helper=", id)
#define SPS_COMPONENT(id) SPS_DETAIL_ANNOTATE("sps.component=", id)
#define SPS_ROOT(id) SPS_DETAIL_ANNOTATE("sps.root=", id)
#define SPS_RETURN_OUTPUT(id) SPS_DETAIL_ANNOTATE("sps.return-output=", id)

#endif
