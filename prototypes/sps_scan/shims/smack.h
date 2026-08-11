#ifndef SMACK_SHIM2_H
#define SMACK_SHIM2_H
typedef void* smack_value_t;
extern smack_value_t __SMACK_value_i(const void*);
extern smack_value_t __SMACK_values_i(const void*, long);
extern smack_value_t __SMACK_return_value_i(void);
extern smack_value_t __SMACK_object_i(const void*, long);
#define __SMACK_value(x)           __SMACK_value_i((const void*)(long)(x))
#define __SMACK_values(x,n)        __SMACK_values_i((const void*)(x), (long)(n))
#define __SMACK_return_value()     __SMACK_return_value_i()
#define __SMACK_return_values(x,n) __SMACK_values_i((const void*)0,(long)(n))
#define __SMACK_object(x,n)        __SMACK_object_i((const void*)(x),(long)(n))
extern void assume(int);
#endif
