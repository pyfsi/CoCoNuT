/* This file generated automatically. */
/*          Do not modify.            */
#include "udf.h"
#include "prop.h"
#include "dpm.h"
extern DEFINE_INIT (temp_ini, d);
UDF_Data udf_data[] = {
{"temp_ini", (void (*)(void))temp_ini, UDF_TYPE_INIT},
};
int n_udf_data = sizeof(udf_data)/sizeof(UDF_Data);
#include "version.h"
void UDF_Inquire_Release(int *major, int *minor, int *revision)
{
  *major = RampantReleaseMajor;
  *minor = RampantReleaseMinor;
  *revision = RampantReleaseRevision;
}
