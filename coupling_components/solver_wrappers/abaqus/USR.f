#define RAMP |ramp|

C==============================================================================
C======================== GLOBAL DATA =========================================
C==============================================================================
      BLOCK DATA

      INTEGER D,N,S
      PARAMETER (D = |dimension|)
      PARAMETER (N = |arraySize|)
      PARAMETER (S = |surfaces|)

      CHARACTER (LEN=80), DIMENSION(S) :: SURFACEIDS
      COMMON /SURF/ SURFACEIDS
      SAVE /SURF/
      DATA SURFACEIDS /|surfaceIDs|/

      DOUBLE PRECISION LOADNEW(D+1,N,S)
#if RAMP
      DOUBLE PRECISION LOADOLD(D+1,N,S)
#endif
      INTEGER FILLED,
#ifdef MPI
     &        K(S),L(S),
#endif
     &        M(S)
      COMMON /TABLE/ LOADNEW,
#if RAMP
     &               LOADOLD,
#endif
     &               FILLED,
#ifdef MPI
     &               K,L,
#endif
     &               M
      SAVE /TABLE/

#ifdef MPI
      INTEGER ID,IDENTIFIED
      COMMON /IDENT/ ID,IDENTIFIED
      SAVE /IDENT/
#else
      INTEGER OP(2,S),ELS(2,N,S)
      COMMON /OPELS/ OP,ELS
      SAVE /OPELS/
#endif

      DATA FILLED/-1/
#ifdef MPI
      DATA IDENTIFIED/-1/
      DATA K/S*1/
      DATA L/S*1/
#endif

      END

#ifdef MPI
C==============================================================================
C======================== IDENTIFY SUBROUTINE =================================
C==============================================================================
      SUBROUTINE IDENTIFY
      
      IMPLICIT NONE
      
      INCLUDE 'mpif.h'

      INTEGER ID,IDENTIFIED,IERROR
      COMMON /IDENT/ ID,IDENTIFIED
      SAVE /IDENT/
      
      IF (|cpus| > 1) THEN
         CALL MPI_COMM_RANK(MPI_COMM_WORLD,ID,IERROR)
         IF (IERROR < 0) THEN
            CALL STDB_ABQERR(-3,'USR-error: problem while identifying')
         END IF
      ELSE
         ID = 0
      END IF
       
      IDENTIFIED = 1
      
      RETURN
      END
#else
C==============================================================================
C======================== LOOKUP SUBROUTINE ===================================
C==============================================================================
      SUBROUTINE LOOKUP(NOEL,R,K)

      IMPLICIT NONE

      INTEGER N,S
      PARAMETER (N = |arraySize|)
      PARAMETER (S = |surfaces|)

      INTEGER OP(2,S),ELS(2,N,S)
      COMMON /OPELS/ OP,ELS
      SAVE /OPELS/

      INTEGER NOEL,R,K,LEFT,MID,RIGHT

      K = 0
      LEFT  = 1
      RIGHT = OP(1,R)
      DO
         IF (LEFT > RIGHT) RETURN
         MID = (LEFT+RIGHT)/2
         IF (NOEL == ELS(1,MID,R)) THEN
            K = MID
            RETURN
         ELSE IF (NOEL < ELS(1,MID,R)) THEN
            RIGHT = MID-1
         ELSE
            LEFT = MID+1
         END IF
      END DO

      RETURN
      END
#endif
     
C==============================================================================
C======================== READDATA SUBROUTINE =================================
C==============================================================================
      SUBROUTINE READDATA(KSTEP)
      
      IMPLICIT NONE
     
      INTEGER D,N,S
      PARAMETER (D = |dimension|)
      PARAMETER (N = |arraySize|)
      PARAMETER (S = |surfaces|)

      DOUBLE PRECISION LOADNEW(D+1,N,S)
#if RAMP
      DOUBLE PRECISION LOADOLD(D+1,N,S)
#endif
      INTEGER FILLED,
#ifdef MPI
     &        K(S),L(S),
#endif
     &        M(S)
      COMMON /TABLE/ LOADNEW,
#if RAMP
     &               LOADOLD,
#endif
     &               FILLED,
#ifdef MPI
     &               K,L,
#endif
     &               M
      SAVE /TABLE/

#ifdef MPI
      INTEGER ID,IDENTIFIED
      COMMON /IDENT/ ID,IDENTIFIED
      SAVE /IDENT/
#else
      INTEGER ID
      INTEGER OP(2,S),ELS(2,N,S)
      COMMON /OPELS/ OP,ELS
      SAVE /OPELS/

      CHARACTER(LEN=40) :: FMT_ELEM
      INTEGER UNIT_ELEM
#endif

      CHARACTER(LEN=40) :: FMT_LOAD
      CHARACTER(LEN=200) :: FILENAME
      INTEGER I,R,UNIT_LOAD,IOS,KSTEP

#ifndef MPI
!$OMP CRITICAL
      IF (FILLED < 0) THEN
#endif

      FMT_LOAD = '(ES27.17E2,|dimension|ES27.17E2)'
      UNIT_LOAD = 100
     
#ifdef MPI
      IF (IDENTIFIED < 0) THEN
         CALL IDENTIFY
      END IF
#else
      ID = 0

      FMT_ELEM = '(I10,BN,I11)'
      UNIT_ELEM = 101

      DO R = 1,S
         WRITE(FILENAME,'(A,A,A,I0,A)') 
     &      '|PWD|',
     &      '/|CSM_dir|/CSM_Time0',
     &      'Surface',(R-1),'Elements.dat'

         OPEN(UNIT=UNIT_ELEM,FILE=FILENAME,STATUS='OLD')
      
         READ(UNIT_ELEM,FMT_ELEM,IOSTAT=IOS) OP(:,R)
         IF (IOS < 0) THEN
            CALL STDB_ABQERR(-3,'USR-error: problem while opening')
         END IF
         IF (OP(1,R) > N) THEN
            CALL STDB_ABQERR(-3,'USR-error: problem with array length')
         END IF
         DO I = 1,OP(1,R)
            READ(UNIT_ELEM,FMT_ELEM,IOSTAT=IOS) ELS(:,I,R)
            IF (IOS < 0) THEN
               CALL STDB_ABQERR(-3,'USR-error: problem while reading')
            END IF
         END DO
         CLOSE(UNIT_ELEM)
      END DO
#endif
      
      DO R = 1,S
         WRITE(FILENAME,'(A,A,I0,A,I0,A,I0,A)') 
     &      '|PWD|',
     &      '/|CSM_dir|/CSM_Time',
     &      KSTEP,'Surface',(R-1),'Cpu',ID,'Input.dat'

         OPEN(UNIT=UNIT_LOAD,FILE=FILENAME,STATUS='OLD')
      
         READ(UNIT_LOAD,'(I)',IOSTAT=IOS) M(R)
         IF (IOS < 0) THEN
            CALL STDB_ABQERR(-3,'USR-error: problem while opening')
         END IF
         IF (M(R) > N) THEN
            CALL STDB_ABQERR(-3,'USR-error: problem with array length')
         END IF
         DO I = 1,M(R)
            READ(UNIT_LOAD,FMT_LOAD,IOSTAT=IOS)
     &         LOADNEW(:,I,R)
            IF (IOS < 0) THEN
               CALL STDB_ABQERR(-3,'USR-error: problem while reading')
            END IF
         END DO
         CLOSE(UNIT_LOAD)

#if RAMP
         WRITE(FILENAME,'(A,A,I0,A,I0,A,I0,A)') 
     &      '|PWD|',
     &      '/|CSM_dir|/CSM_Time',
     &      (KSTEP-1),'Surface',(R-1),'Cpu',ID,'Input.dat'

         OPEN(UNIT=UNIT_LOAD,FILE=FILENAME,STATUS='OLD')
      
         READ(UNIT_LOAD,'(I)',IOSTAT=IOS) M(R)
         IF (IOS < 0) THEN
            CALL STDB_ABQERR(-3,'USR-error: problem while opening')
         END IF
         IF (M(R) > N) THEN
            CALL STDB_ABQERR(-3,'USR-error: problem with array length')
         END IF
         DO I = 1,M(R)
            READ(UNIT_LOAD,FMT_LOAD,IOSTAT=IOS)
     &         LOADOLD(:,I,R)
            IF (IOS < 0) THEN
               CALL STDB_ABQERR(-3,'USR-error: problem while reading')
            END IF
         END DO
         CLOSE(UNIT_LOAD)
#endif
      END DO

      FILLED = 1

#ifndef MPI
      END IF
!$OMP END CRITICAL
#endif

      RETURN
      END

C==============================================================================
C======================== DLOAD SUBROUTINE ====================================
C==============================================================================

      SUBROUTINE DLOAD(F,KSTEP,KINC,TIME,NOEL,NPT,LAYER,KSPT,
     &   COORDS,JLTYP,SNAME)

      IMPLICIT NONE

      INTEGER D,N,S
      PARAMETER (D = |dimension|)
      PARAMETER (N = |arraySize|)
      PARAMETER (S = |surfaces|)
      CHARACTER (LEN=80), DIMENSION(S) :: SURFACEIDS
      COMMON /SURF/ SURFACEIDS
      SAVE /SURF/

      DOUBLE PRECISION LOADNEW(D+1,N,S)
#if RAMP
      DOUBLE PRECISION LOADOLD(D+1,N,S),DT
#endif
      INTEGER FILLED,
#ifdef MPI
     &        K(S),L(S),
#endif
     &        M(S)
      COMMON /TABLE/ LOADNEW,
#if RAMP
     &               LOADOLD,
#endif
     &               FILLED,
#ifdef MPI
     &               K,L,
#endif
     &               M
      SAVE /TABLE/

      DOUBLE PRECISION F,TIME(2),COORDS(D)
      CHARACTER(LEN=80) :: SNAME
      INTEGER KSTEP,KINC,NOEL,NPT,LAYER,KSPT,JLTYP,R
      LOGICAL :: FOUND

#ifndef MPI
      INTEGER K
      INTEGER OP(2,S),ELS(2,N,S)
      COMMON /OPELS/ OP,ELS
      SAVE /OPELS/
#endif

      IF (FILLED < 0) THEN
         CALL READDATA(KSTEP)
      END IF

#if RAMP
      IF (|deltaT| > 0.0) THEN
         DT = |deltaT|
      ELSE
         DT = 1.0
      END IF
#endif

      FOUND  = .FALSE.
      IF (S > 1) THEN
         DO R = 1,S
            IF (INDEX(SNAME, TRIM(SURFACEIDS(R))) > 0) THEN
               FOUND = .TRUE.
               EXIT
            END IF
         END DO
         IF (.NOT. FOUND) THEN
            PRINT *, 'USR-abort: no matching surface name found for Mod
     &elPart.'
            CALL FLUSH(6)
            CALL STDB_ABQERR(-3,'USR-abort: no matching surface name fo
     &und for ModelPart.')
         END IF
      ELSE
         R = 1
      END IF
#ifdef MPI
#if RAMP
      F = LOADNEW(1,K(R),R)*(TIME(1)/DT)
     &   +LOADOLD(1,K(R),R)*(1.0-TIME(1)/DT)
#else
      F = LOADNEW(1,K(R),R)
#endif

      K(R) = K(R)+1
      IF (K(R) == (M(R)+1)) THEN
         K(R) = 1
      END IF
#else
      CALL LOOKUP(NOEL,R,K)
      K = ELS(2,K,R)+NPT

#if RAMP
      F = LOADNEW(1,K,R)*(TIME(1)/DT)
     &   +LOADOLD(1,K,R)*(1.0-TIME(1)/DT)
#else
      F = LOADNEW(1,K,R)
#endif
#endif

      RETURN
      END
      
C==============================================================================
C======================== UTRACLOAD SUBROUTINE ================================
C==============================================================================

      SUBROUTINE UTRACLOAD(ALPHA,T_USER,KSTEP,KINC,TIME,
     &   NOEL,NPT,COORDS,DIRCOS,JLTYP,SNAME)

      IMPLICIT NONE

      INTEGER D,N,S
      PARAMETER (D = |dimension|)
      PARAMETER (N = |arraySize|)
      PARAMETER (S = |surfaces|)
      CHARACTER (LEN=80), DIMENSION(S) :: SURFACEIDS
      COMMON /SURF/ SURFACEIDS
      SAVE /SURF/

      DOUBLE PRECISION LOADNEW(D+1,N,S)
#if RAMP
      DOUBLE PRECISION LOADOLD(D+1,N,S)
#endif
      INTEGER FILLED,
#ifdef MPI
     &        K(S),L(S),
#endif
     &        M(S)
      COMMON /TABLE/ LOADNEW,
#if RAMP
     &               LOADOLD,
#endif
     &               FILLED,
#ifdef MPI
     &               K,L,
#endif
     &               M
      SAVE /TABLE/

      DOUBLE PRECISION ALPHA,T_USER(D),TIME(2),COORDS(D),DIRCOS(3,3)
      CHARACTER(LEN=80) :: SNAME
      INTEGER KSTEP,KINC,NOEL,NPT,JLTYP,R
      LOGICAL :: FOUND

#ifndef MPI
      INTEGER L
      INTEGER OP(2,S),ELS(2,N,S)
      COMMON /OPELS/ OP,ELS
      SAVE /OPELS/
#endif

      IF (FILLED < 0) THEN
         CALL READDATA(KSTEP)
      END IF

      FOUND  = .FALSE.
      IF (S > 1) THEN
         DO R = 1,S
            IF (INDEX(SNAME, TRIM(SURFACEIDS(R))) > 0) THEN
               FOUND = .TRUE.
               EXIT
            END IF
         END DO
         IF (.NOT. FOUND) THEN
            PRINT *, 'USR-abort: no matching surface name found for Mod
     &elPart.'
            CALL FLUSH(6)
            CALL STDB_ABQERR(-3,'USR-abort: no matching surface name fo
     &und for ModelPart.')
         END IF
      ELSE
         R = 1
      END IF

#ifdef MPI
      T_USER = LOADNEW(2:D+1,L(R),R)

      L(R) = L(R)+1
      IF (L(R) == (M(R)+1)) THEN
         L(R) = 1
      END IF
#else
      CALL LOOKUP(NOEL,R,L)
      L = ELS(2,L,R)+NPT

      T_USER = LOADNEW(2:D+1,L,R)
#endif

      ALPHA = SQRT(SUM(T_USER**2))
      IF (ALPHA /= 0.0) THEN
         T_USER = T_USER/ALPHA
      ELSE
         T_USER(1) = 1.0
      END IF
      
      RETURN
      END
